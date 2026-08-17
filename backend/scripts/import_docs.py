import os
import sys
import markdown
from pathlib import Path

# Add backend to sys.path to allow importing app modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.documents import DocWorkspace, DocPage, DocPageVersion, PageType, PageStatus

WORKSPACE_NAME = "Platform User Guide"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "user-guide" / "forms-and-entities"

DOCS_MAP = [
    {"title": "Introduction & Philosophy", "filename": "README.md", "is_root": True},
    {"title": "Entity Builder Guide", "filename": "entity-builder.md", "is_root": False},
    {"title": "Form Builder Guide", "filename": "form-builder.md", "is_root": False},
    {"title": "Data Management & Records", "filename": "data-management.md", "is_root": False},
    {"title": "Best Practices", "filename": "best-practices.md", "is_root": False},
]

def import_documents():
    db: Session = SessionLocal()
    try:
        # 1. Create/Find Workspace
        workspace = db.query(DocWorkspace).filter(DocWorkspace.name == WORKSPACE_NAME).first()
        if not workspace:
            print(f"Creating workspace: {WORKSPACE_NAME}")
            workspace = DocWorkspace(name=WORKSPACE_NAME, created_by="system_importer")
            db.add(workspace)
            db.flush()
        else:
            print(f"Using existing workspace: {WORKSPACE_NAME}")
            # Delete existing pages to ensure clean state and draft mode
            print(f"Cleaning existing pages in '{WORKSPACE_NAME}'...")
            db.query(DocPage).filter(DocPage.workspace_id == workspace.id).delete()
            db.flush()

        # 2. Process Files
        root_page_id = None
        for i, doc in enumerate(DOCS_MAP):
            file_path = DOCS_DIR / doc["filename"]
            if not file_path.exists():
                print(f"Warning: {file_path} not found. Skipping.")
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                content_md = f.read()
            
            # Convert Markdown to HTML for TipTap compatibility
            content_html = markdown.markdown(content_md, extensions=['extra', 'codehilite', 'toc'])

            # Create page
            print(f"Creating page: {doc['title']}")
            page = DocPage(
                workspace_id=workspace.id,
                title=doc["title"],
                type=PageType.guide,
                status=PageStatus.draft,
                parent_id=root_page_id if not doc["is_root"] else None,
                sort_order=i,
                created_by="system_importer"
            )
            db.add(page)
            db.flush()

            if doc["is_root"]:
                root_page_id = page.id

            # Create version with both text and HTML (passed as JSON string for TipTap)
            version = DocPageVersion(
                page_id=page.id,
                version_number=1,
                content_json=content_html, # TipTap parses HTML strings
                content_text=content_md,
            )
            db.add(version)

        db.commit()
        print("Import successful! All documents are in DRAFT mode.")

    except Exception as e:
        db.rollback()
        print(f"Error during import: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    import_documents()
