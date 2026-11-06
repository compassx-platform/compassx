import time

from app.sandbox.models import SandboxProgress, SandboxSpec, SandboxStatus
from app.sandbox.shared.support import logger


class EnsureSandbox:
    def execute(self, service, spec: SandboxSpec):
        start_time = time.time()
        c_key = spec.consumer_key or spec.sandbox_id

        existing = service.find_active_sandbox(
            sandbox_id=spec.sandbox_id,
            consumer_key=c_key,
            consumer_module=spec.consumer_module,
        )

        if existing:
            driver = service._get_driver_for_mode(existing.runtime_mode)
            live_status = driver.get_status(existing)
            existing.status = live_status
            existing.endpoints = driver.get_endpoints(existing)

            if live_status in (SandboxStatus.READY, SandboxStatus.RUNNING):
                existing.progress = SandboxProgress(
                    stage="ready",
                    step_index=len(spec.init_scripts) + 2,
                    total_steps=len(spec.init_scripts) + 2,
                    step_name="Ready",
                    message="Sandbox is active and ready",
                    percent=100,
                    elapsed_seconds=0.0,
                )
                logger.info("ensure_sandbox: Returning existing active sandbox %s (%s)", existing.name, existing.id)
                return existing

            if live_status in (SandboxStatus.SUSPENDED, SandboxStatus.STOPPED):
                existing.progress = SandboxProgress(
                    stage="starting",
                    step_index=1,
                    total_steps=2,
                    step_name="Resume Compute",
                    message="Resuming suspended sandbox compute...",
                    percent=50,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )
                service.resume_sandbox(existing.id)
                existing.endpoints = driver.get_endpoints(existing)
                existing.progress = SandboxProgress(
                    stage="ready",
                    step_index=2,
                    total_steps=2,
                    step_name="Ready",
                    message="Sandbox resumed successfully",
                    percent=100,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )
                return existing

            if live_status in (SandboxStatus.PROVISIONING, SandboxStatus.INITIALIZING):
                return existing

        total_steps = 2 + len(spec.init_scripts)

        if spec.consumer_key and "compassx.consumer_key" not in spec.labels:
            spec.labels["compassx.consumer_key"] = spec.consumer_key

        driver = service._get_driver_for_mode(spec.runtime_mode)

        initial_progress = SandboxProgress(
            stage="allocating",
            step_index=1,
            total_steps=total_steps,
            step_name="Allocate Compute",
            message=f"Allocating compute sandbox for '{spec.name}'...",
            percent=10,
            elapsed_seconds=round(time.time() - start_time, 2),
        )

        instance = driver.provision(spec)
        instance.consumer_key = spec.consumer_key
        instance.status = SandboxStatus.PROVISIONING
        instance.progress = initial_progress
        service._instances[instance.id] = instance

        instance.progress = SandboxProgress(
            stage="starting",
            step_index=2,
            total_steps=total_steps,
            step_name="Start Runtime",
            message="Starting sandbox container environment...",
            percent=25,
            elapsed_seconds=round(time.time() - start_time, 2),
        )

        if spec.init_scripts:
            instance.status = SandboxStatus.INITIALIZING
            for idx, script in enumerate(spec.init_scripts):
                step_num = 3 + idx
                pct = int(25 + ((idx) / max(1, len(spec.init_scripts))) * 70)
                instance.progress = SandboxProgress(
                    stage="initializing",
                    step_index=step_num,
                    total_steps=total_steps,
                    step_name=script.name,
                    message=f"Running step [{idx + 1}/{len(spec.init_scripts)}]: {script.name}...",
                    percent=pct,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )

                res = driver.exec_command(
                    instance,
                    command=script.command,
                    working_dir=script.working_dir or instance.working_dir,
                    env=script.env,
                    timeout=script.timeout_seconds,
                )

                if not res.success and not script.ignore_failure:
                    err_msg = f"Init step '{script.name}' failed with exit code {res.exit_code}: {res.stderr or res.stdout}"
                    logger.error(err_msg)
                    instance.status = SandboxStatus.FAILED
                    instance.error_message = err_msg
                    instance.progress = SandboxProgress(
                        stage="failed",
                        step_index=step_num,
                        total_steps=total_steps,
                        step_name=script.name,
                        message=err_msg,
                        percent=pct,
                        elapsed_seconds=round(time.time() - start_time, 2),
                        details={"exit_code": res.exit_code, "stderr": res.stderr, "stdout": res.stdout},
                    )
                    return instance

        if instance.status == SandboxStatus.FAILED:
            instance.progress = SandboxProgress(
                stage="failed",
                step_index=total_steps,
                total_steps=total_steps,
                step_name="Failed",
                message=instance.error_message or "Sandbox startup failed",
                percent=100,
                elapsed_seconds=round(time.time() - start_time, 2),
                details={"error": instance.error_message},
            )
            logger.error("Sandbox '%s' (%s) FAILED in %.2fs: %s", instance.name, instance.id, time.time() - start_time, instance.error_message)
            return instance

        if instance.status == SandboxStatus.PROVISIONING:
            instance.progress = SandboxProgress(
                stage="starting",
                step_index=2,
                total_steps=total_steps,
                step_name="Provisioning",
                message="Sandbox compute is provisioning in cluster...",
                percent=50,
                elapsed_seconds=round(time.time() - start_time, 2),
            )
            return instance

        instance.status = SandboxStatus.READY
        instance.endpoints = driver.get_endpoints(instance)
        instance.progress = SandboxProgress(
            stage="ready",
            step_index=total_steps,
            total_steps=total_steps,
            step_name="Ready",
            message="Sandbox environment is ready",
            percent=100,
            elapsed_seconds=round(time.time() - start_time, 2),
        )
        logger.info("Sandbox '%s' (%s) is READY in %.2fs", instance.name, instance.id, time.time() - start_time)
        return instance


def ensure_sandbox(service, spec):
    return EnsureSandbox().execute(service, spec)
