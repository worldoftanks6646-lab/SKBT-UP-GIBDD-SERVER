from html import escape
import secrets
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import Device, Employee, Role, RoleAssignment, RoleCode, Witness
from app.services.admin_auth import SESSION_COOKIE, create_session, read_session, verify_password
from app.services.push_service import PushService
from app.services.role_service import EmployeeNotFoundError, RoleConflictError, RolePermissionDeniedError, RoleService


router = APIRouter(prefix="/admin", include_in_schema=False)


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
:root{{--bg:#f4f7fb;--card:#fff;--ink:#172033;--muted:#64748b;--line:#dce3ed;--blue:#2457e6;--red:#c93636}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px system-ui,-apple-system,Segoe UI,sans-serif}}
.wrap{{max-width:1200px;margin:0 auto;padding:28px 18px}}.top{{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:22px}}
h1{{font-size:26px;margin:0}}.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 5px 20px #21335a0d}}
input,select,button{{font:inherit;border:1px solid #cbd5e1;border-radius:8px;padding:10px 12px}}input,select{{background:#fff}}button{{cursor:pointer;background:var(--blue);color:#fff;border-color:var(--blue);font-weight:600}}button.danger{{background:#fff;color:var(--red);border-color:#efb6b6}}
.login{{max-width:420px;margin:12vh auto}}.login input{{width:100%;margin:6px 0 14px}}.login button{{width:100%}}
.toolbar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}}.toolbar input{{flex:1;min-width:240px}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:12px 9px;border-bottom:1px solid var(--line);vertical-align:middle}}th{{color:var(--muted);font-size:12px;text-transform:uppercase}}code{{font-size:12px}}.role{{display:flex;gap:7px;align-items:center;flex-wrap:wrap}}.pill{{display:inline-block;padding:4px 8px;border-radius:99px;background:#edf2ff;color:#2349ad}}.muted{{color:var(--muted)}}.flash{{padding:11px 13px;margin-bottom:14px;border-radius:8px;background:#e8f7ed;color:#176b34}}.error{{background:#fff0f0;color:#9e2626}}@media(max-width:760px){{table,tbody,tr,td{{display:block}}thead{{display:none}}tr{{padding:12px 0;border-bottom:1px solid var(--line)}}td{{border:0;padding:5px}}}}
</style></head><body>{body}</body></html>""")


def _session(request: Request):
    return read_session(request.cookies.get(SESSION_COOKIE))


def _require_session(request: Request):
    session = _session(request)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return session


def _verify_csrf(request: Request, csrf_token: str):
    session = _require_session(request)
    if not secrets.compare_digest(session.csrf_token, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    return session


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None):
    if _session(request):
        return RedirectResponse("/admin", status_code=303)
    message = '<div class="flash error">Неверный логин или пароль</div>' if error else ""
    return _page("Вход", f"""<main class="wrap"><section class="card login"><h1>Админ-панель</h1><p class="muted">Управление устройствами и ролями сотрудников</p>{message}<form method="post" action="/admin/login"><label>Логин</label><input name="username" autocomplete="username" required><label>Пароль</label><input type="password" name="password" autocomplete="current-password" required><button>Войти</button></form></section></main>""")


@router.post("/login")
async def login(username: str = Form(), password: str = Form()):
    if username != settings.ADMIN_USERNAME or not verify_password(password):
        return RedirectResponse("/admin/login?error=1", status_code=303)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        create_session(username),
        max_age=8 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/admin",
    )
    return response


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form()):
    _verify_csrf(request, csrf_token)
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/admin")
    return response


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db), ok: str | None = None, error: str | None = None):
    session = _session(request)
    if session is None:
        return RedirectResponse("/admin/login", status_code=303)
    active_role = (
        select(RoleAssignment.employee_id, Role.code)
        .join(Role, Role.id == RoleAssignment.role_id)
        .where(RoleAssignment.revoked_at.is_(None))
        .subquery()
    )
    rows = (
        await db.execute(
            select(Device, Employee.id, Witness.id, active_role.c.code)
            .outerjoin(Employee, Employee.device_id == Device.id)
            .outerjoin(Witness, Witness.device_id == Device.id)
            .outerjoin(active_role, active_role.c.employee_id == Employee.id)
            .order_by(Device.registered_at.desc())
        )
    ).all()
    table_rows = []
    for device, employee_id, witness_id, role in rows:
        identity = employee_id or witness_id
        role_value = role.value if role else ""
        actions = '<span class="muted">—</span>'
        if employee_id and str(device.id) != settings.ADMIN_ACTOR_DEVICE_ID:
            options = "".join(
                f'<option value="{item.value}" {"selected" if role_value == item.value else ""}>{item.value}</option>'
                for item in RoleCode
            )
            actions = f'''<div class="role"><form method="post" action="/admin/employees/{employee_id}/role"><input type="hidden" name="csrf_token" value="{session.csrf_token}"><select name="role">{options}</select><button>Сохранить</button></form>'''
            if role_value:
                actions += f'''<form method="post" action="/admin/employees/{employee_id}/role/revoke"><input type="hidden" name="csrf_token" value="{session.csrf_token}"><button class="danger">Снять</button></form>'''
            actions += "</div>"
        elif employee_id:
            actions = '<span class="muted">Служебный начальник</span>'
        table_rows.append(f"""<tr data-search="{device.id} {device.type.value} {role_value} {device.platform}"><td><span class="pill">{device.type.value}</span></td><td><code>{device.id}</code><br><span class="muted">{identity or ''}</span></td><td>{escape(device.platform)}<br><span class="muted">v{escape(device.app_version)}</span></td><td>{role_value or '—'}</td><td>{actions}</td></tr>""")
    flash = f'<div class="flash">{escape(ok)}</div>' if ok else (f'<div class="flash error">{escape(error)}</div>' if error else "")
    body = f"""<main class="wrap"><header class="top"><div><h1>Устройства и роли</h1><div class="muted">Всего устройств: {len(rows)}</div></div><form method="post" action="/admin/logout"><input type="hidden" name="csrf_token" value="{session.csrf_token}"><button class="danger">Выйти</button></form></header>{flash}<section class="card"><div class="toolbar"><input id="search" placeholder="Поиск по device ID, типу, роли или платформе"><select id="type"><option value="">Все устройства</option><option value="employee">Сотрудники</option><option value="witness">Очевидцы</option></select></div><div style="overflow:auto"><table><thead><tr><th>Тип</th><th>Device ID / ID профиля</th><th>Платформа</th><th>Роль</th><th>Действие</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></div></section></main><script>const q=document.querySelector('#search'),t=document.querySelector('#type'),rs=[...document.querySelectorAll('tbody tr')];function f(){{let s=q.value.toLowerCase(),v=t.value;rs.forEach(r=>r.hidden=!(r.dataset.search.toLowerCase().includes(s)&&(!v||r.dataset.search.includes(v))))}}q.oninput=f;t.onchange=f;</script>"""
    return _page("Админ-панель", body)


def _actor_device_id() -> UUID:
    if not settings.ADMIN_ACTOR_DEVICE_ID:
        raise HTTPException(status_code=503, detail="ADMIN_ACTOR_DEVICE_ID is not configured")
    return UUID(settings.ADMIN_ACTOR_DEVICE_ID)


def _dashboard_redirect(key: str, message: str) -> RedirectResponse:
    return RedirectResponse(f"/admin?{urlencode({key: message})}", status_code=303)


async def _ensure_target_is_not_actor(db: AsyncSession, employee_id: UUID) -> None:
    target_device_id = await db.scalar(
        select(Employee.device_id).where(Employee.id == employee_id)
    )
    if target_device_id is not None and target_device_id == _actor_device_id():
        raise RolePermissionDeniedError(
            "Роль служебного начальника нельзя изменить через админ-панель"
        )


@router.post("/employees/{employee_id}/role")
async def change_role(request: Request, employee_id: UUID, role: RoleCode = Form(), csrf_token: str = Form(), db: AsyncSession = Depends(get_db)):
    _verify_csrf(request, csrf_token)
    try:
        await _ensure_target_is_not_actor(db, employee_id)
        result = await RoleService.assign(db, employee_id, _actor_device_id(), role)
        await PushService.notify_employee(db, result.employee_id, "employee_role_changed", "ГИБДД-Очевидец", "Ваша роль изменена", {"assignment_id": str(result.id), "role": result.role.value})
        return _dashboard_redirect("ok", f"Роль изменена на {role.value}")
    except (EmployeeNotFoundError, RolePermissionDeniedError, RoleConflictError, ValueError) as exc:
        return _dashboard_redirect("error", str(exc))


@router.post("/employees/{employee_id}/role/revoke")
async def remove_role(request: Request, employee_id: UUID, csrf_token: str = Form(), db: AsyncSession = Depends(get_db)):
    _verify_csrf(request, csrf_token)
    try:
        await _ensure_target_is_not_actor(db, employee_id)
        result = await RoleService.revoke(db, employee_id, _actor_device_id())
        await PushService.notify_employee(db, result.employee_id, "employee_role_revoked", "ГИБДД-Очевидец", "Ваша роль снята", {"assignment_id": str(result.id), "role": result.role.value})
        return _dashboard_redirect("ok", "Роль снята")
    except (EmployeeNotFoundError, RolePermissionDeniedError, RoleConflictError, ValueError) as exc:
        return _dashboard_redirect("error", str(exc))
