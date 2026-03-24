import json
from api.database import ActivityLog


def log_activity(db, user_id: str, action: str,
                 resource_type: str = None, resource_id: str = None,
                 detail: dict = None, workspace_id: str = None,
                 ip_address: str = None):
    db.add(ActivityLog(
        user_id=user_id, workspace_id=workspace_id,
        action=action, resource_type=resource_type,
        resource_id=resource_id,
        detail=json.dumps(detail) if detail else None,
        ip_address=ip_address,
    ))
