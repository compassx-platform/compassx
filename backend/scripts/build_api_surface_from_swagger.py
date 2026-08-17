import json
from pathlib import Path

class BuildApiSurfaceFromSwaggerTool:
    name = "build_api_surface_from_swagger"
    description = """
    Read a Swagger/OpenAPI spec and generate a compressed
    api-surface.md optimised for agent consumption.
    Run once when the API changes. Output saved to shared storage.
    """
    schema = {
        "type": "object",
        "properties": {
            "swagger_url": {
                "type": "string",
                "description": "URL to swagger.json or swagger.yaml e.g. http://localhost:3000/api-docs"
            },
            "swagger_file": {
                "type": "string",
                "description": "Local path to swagger file. Use if URL not available."
            },
            "output_name": {
                "type": "string",
                "description": "Service name e.g. asset-manager"
            }
        },
        "required": ["output_name"]
    }

    def execute(self, args, context) -> dict:
        import yaml, requests as req

        # Load swagger from URL or file
        if args.get("swagger_url"):
            resp = req.get(args["swagger_url"], timeout=10)
            print(f"resp data: {resp.text[:200]}")  # Debug: print first 200 chars of response
            spec = resp.json()
        elif args.get("swagger_file"):
            content = Path(args["swagger_file"]).read_text()
            spec = yaml.safe_load(content) if content.strip().startswith("{") == False else json.loads(content)
        else:
            return {"success": False, "error": "Provide swagger_url or swagger_file"}

        # Generate compressed markdown
        md = self._compress(spec, args["output_name"])

        # Save to shared storage
        out_dir = Path(f"/shared/{context.workspace_id}/{args['output_name']}")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "api-surface.md"
        out_path.write_text(md)
        print(f"full path: {out_path.resolve()}")  # Debug: print full path to output file

        return {
            "success": True,
            "output_path": str(out_path),
            "endpoints_documented": md.count("##") - 1,
            "token_estimate": len(md.split()) * 1.3
        }

    def _compress(self, spec: dict, name: str) -> str:
        lines = [
            f"# {name} API Surface",
            f"Base URL: {self._base_url(spec)}",
            ""
        ]

        for path, methods in spec.get("paths", {}).items():
            for method, details in methods.items():
                if method not in ["get","post","put","patch","delete"]:
                    continue

                lines.append(f"## {method.upper()} {path}")

                # Summary
                if details.get("summary"):
                    lines.append(details["summary"])

                # Request body — compressed
                body = self._extract_body(details, spec)
                if body:
                    lines.append(f"Body: {body}")

                # Query params — compressed
                params = self._extract_params(details)
                if params:
                    lines.append(f"Params: {params}")

                # Responses — only success + main errors
                responses = self._extract_responses(details)
                if responses:
                    lines.append(f"Returns: {responses}")

                # Error codes
                errors = self._extract_errors(details, spec)
                if errors:
                    lines.append(f"Errors: {errors}")

                lines.append("")

        return "\n".join(lines)

    def _base_url(self, spec):
        servers = spec.get("servers", [])
        return servers[0].get("url", "") if servers else ""

    def _extract_body(self, details, spec):
        content = details.get("requestBody", {}).get("content", {})
        schema = content.get("application/json", {}).get("schema", {})
        if "$ref" in schema:
            schema = self._resolve_ref(schema["$ref"], spec)
        props = schema.get("properties", {})
        required = schema.get("required", [])
        if not props:
            return None
        parts = []
        for name, info in props.items():
            marker = "*" if name in required else "?"
            type_str = info.get("type", info.get("$ref", "object").split("/")[-1])
            parts.append(f"{name}{marker}:{type_str}")
        return "{ " + ", ".join(parts) + " }  (* = required)"

    def _extract_params(self, details):
        params = details.get("parameters", [])
        query = [p for p in params if p.get("in") == "query"]
        if not query:
            return None
        parts = []
        for p in query:
            marker = "*" if p.get("required") else "?"
            parts.append(f"{p['name']}{marker}:{p.get('schema',{}).get('type','string')}")
        return ", ".join(parts)

    def _extract_responses(self, details):
        for code in ["200", "201"]:
            resp = details.get("responses", {}).get(code, {})
            content = resp.get("content", {}).get("application/json", {})
            schema = content.get("schema", {})
            if schema.get("properties"):
                props = list(schema["properties"].keys())
                return "{ " + ", ".join(props[:6]) + (" ..." if len(props) > 6 else "") + " }"
        return None

    def _extract_errors(self, details, spec):
        errors = []
        for code, resp in details.get("responses", {}).items():
            if code.startswith("4") or code.startswith("5"):
                desc = resp.get("description", "")
                errors.append(f"{code}:{desc[:40]}")
        return ", ".join(errors) if errors else None

    def _resolve_ref(self, ref, spec):
        parts = ref.lstrip("#/").split("/")
        result = spec
        for part in parts:
            result = result.get(part, {})
        return result

def main():
    tool = BuildApiSurfaceFromSwaggerTool()
    args = {
        "swagger_file": "D:\\vishal_vora\\personal\\external_compass\\repos\\core-opus\\backend\\scripts\\asset_manager_swagger.json",
        "output_name": "asset-manager"
    }
    context = type("Context", (), {"workspace_id": "12345"})
    result = tool.execute(args, context)
    print(result)

if __name__ == "__main__":
    main()