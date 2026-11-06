from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def create_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
    request: Request = None,
):
    # Validate slug uniqueness
    if db.query(Workspace).filter(Workspace.slug == body.slug).first():
        raise HTTPException(status_code=400, detail="Workspace slug already exists")

    # Handle managed storage vs custom storage config
    storage_backend = body.storage_backend or "managed"
    if storage_backend == "managed" or not body.storage_config:
        storage_backend = "managed"
        encrypted_config = {}
    else:
        # Validate custom storage config (test blob write)
        try:
            validate_storage_config(storage_backend, body.storage_config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        # Encrypt sensitive fields
        encrypted_config = encrypt_storage_config(body.storage_config)

    ws_id = str(uuid4())
    ws = Workspace(
        id=ws_id,
        account_id=admin.account_id,
        name=body.name,
        slug=body.slug,
        storage_backend=storage_backend,
        storage_config=encrypted_config,
        created_by=admin.id,
    )
    db.add(ws)
    db.flush()

    # Auto-add creating admin as workspace admin member
    db.add(WorkspaceMembership(
        workspace_id=ws_id,
        principal_id=admin.id,
        role="admin",
        granted_by=admin.id,
    ))

    # Also add UmWorkspaceRoleAssignment in system_db (User Manager v1 topology)
    try:
        from app.database import SystemSessionLocal
        if SystemSessionLocal:
            sys_db = SystemSessionLocal()
            try:
                from app.user_manager.models.system_models import UmWorkspaceRoleAssignment
                with sys_db.begin_nested():
                    sys_db.add(UmWorkspaceRoleAssignment(
                        workspace_id=ws_id,
                        principal_id=admin.id,
                        principal_type="user",
                        role_id="workspace_admin",
                        is_default=True,
                        granted_by=admin.id,
                    ))
                sys_db.commit()
            except Exception as sys_err:
                logger.warning("Could not add system workspace role assignment: %s", sys_err)
            finally:
                sys_db.close()
    except Exception as sys_err:
        logger.warning("Could not open system DB for workspace role assignment: %s", sys_err)

    # Auto-create and bind workspace-specific default catalog
    try:
        import re
        from app.catalog.binding_service import CatalogBindingService
        from app.catalog.schemas import BindingCreate, CatalogPrivilege
        from app.catalog.models import UnifiedCatalog
        
        # Normalize workspace name to valid catalog name
        normalized_name = ws.name.lower().replace(" ", "_").replace("-", "_")
        normalized_name = re.sub(r'[^a-z0-9_]', '', normalized_name)
        if not normalized_name:
            normalized_name = "workspace"
        catalog_name = f"{normalized_name}_default"
        
        # Check if catalog already exists
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            catalog = UnifiedCatalog(
                name=catalog_name,
                description=f"Default catalog for workspace {ws.name}",
                catalog_type="iceberg",
                created_by="system",
            )
            db.add(catalog)
            db.flush()

        binding_service = CatalogBindingService(db)
        await binding_service.bind_catalog(
            workspace_id=ws_id,
            data=BindingCreate(
                catalog_name=catalog_name,
                privilege=CatalogPrivilege.READ_WRITE,
                is_default=True,
            ),
            bound_by="system",
        )

        # Auto-create default schema
        from app.catalog.models import UnifiedCatalogNotebook, UnifiedCatalogSchema, UnifiedCatalogVolume
        schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == catalog.id,
            UnifiedCatalogSchema.name == "default",
        ).first()
        if not schema:
            schema = UnifiedCatalogSchema(
                catalog_id=catalog.id,
                name="default",
                description="Default schema",
                created_by=admin.id,
            )
            db.add(schema)
            db.flush()

        # Auto-create default volume for files and datasets
        volume = db.query(UnifiedCatalogVolume).filter(
            UnifiedCatalogVolume.schema_id == schema.id,
            UnifiedCatalogVolume.name == "sample_data",
        ).first()
        if not volume:
            volume = UnifiedCatalogVolume(
                schema_id=schema.id,
                name="sample_data",
                description="Default storage volume for files and datasets",
                owner=admin.name or admin.email or admin.id,
                created_by=admin.id,
            )
            db.add(volume)
            db.flush()

        # Auto-create getting-started notebook with platform code references
        existing_nb = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.schema_id == schema.id,
            UnifiedCatalogNotebook.name == "getting_started",
        ).first()
        if not existing_nb:
            from app.catalog.service import _write_notebook_content
            from app.workspace.starter_notebook import build_getting_started_notebook

            nb_id = str(uuid4())
            rel_path = f"{nb_id}.ipynb"
            nb_content = build_getting_started_notebook(
                catalog_name=catalog_name,
                schema_name="default",
                volume_name="sample_data",
            )
            try:
                await _write_notebook_content(db, schema, rel_path, nb_content)
            except Exception as nb_write_err:
                logger.warning("Could not write starter notebook content to storage: %s", nb_write_err)

            starter_nb = UnifiedCatalogNotebook(
                id=nb_id,
                schema_id=schema.id,
                catalog_name=catalog_name,
                schema_name="default",
                name="getting_started",
                blob_path=rel_path,
                owner=admin.name or admin.email or admin.id,
                comment="Platform reference guide: Volumes (read/write), AI Agent Tools, and SQL querying",
                created_by=admin.id,
                updated_by=admin.id,
            )
            db.add(starter_nb)
            db.flush()

            try:
                from app.catalog.search_indexer import enqueue_asset_for_embedding
                enqueue_asset_for_embedding(
                    db,
                    object_type="notebook",
                    source_object_id=starter_nb.id,
                    catalog_name=catalog_name,
                    schema_name="default",
                    object_name=starter_nb.name,
                    description=starter_nb.comment,
                )
            except Exception:
                pass

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create workspace due to catalog creation/binding error: {exc}"
        )
    db.refresh(ws)
    result = WorkspaceOut(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        status=ws.status,
        storage_backend=ws.storage_backend,
        url=f"/w/{ws.slug}",
        created_at=ws.created_at,
    )

    # Auto-ensure default DuckDB compute and SQL warehouse for the new workspace
    try:
        from app.database import SystemSessionLocal
        from app.compute.services.workspace_defaults import ensure_workspace_default_resources
        if SystemSessionLocal:
            sys_db = SystemSessionLocal()
            try:
                runtime_manager = getattr(getattr(request, "app", None), "state", None) and getattr(request.app.state, "runtime_manager", None)
                ensure_workspace_default_resources(
                    sys_db,
                    workspace_id=ws_id,
                    created_by=admin.id,
                    user_id=admin.id,
                    runtime_manager=runtime_manager,
                )
            except Exception as res_err:
                logger.warning("Could not auto-ensure default compute/warehouse for workspace %s: %s", ws_id, res_err)
            finally:
                sys_db.close()
    except Exception as res_err:
        logger.warning("Could not open system DB for default compute/warehouse creation: %s", res_err)

    # Invalidate entry point cache so post-login routing sees the new workspace
    try:
        from app.user_manager.entry_point import invalidate_entry_point_cache
        invalidate_entry_point_cache(admin.id)
    except Exception:
        pass

    return result
