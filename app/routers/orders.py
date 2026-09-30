# 订单相关接口，都要求登录态
from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..auth import get_current_user
from ..schemas import OrderCreateReq, OrderStatusReq

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("")
def create_order(req: OrderCreateReq, _: dict = Depends(get_current_user)):
    # 下单的用户必须存在
    if not db.query_one("SELECT id FROM users WHERE id=?", (req.user_id,)):
        raise HTTPException(status_code=404, detail="下单用户不存在")
    oid = db.insert(
        """INSERT INTO orders (user_id, product_id, product_name, quantity, amount)
           VALUES (?,?,?,?,?)""",
        (req.user_id, req.product_id, req.product_name, req.quantity, req.amount),
    )
    return {"code": 0, "message": "ok", "data": {"order_id": oid, "status": "pending"}}


@router.get("")
def list_orders(
    user_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
    _: dict = Depends(get_current_user),
):
    if user_id:
        rows = db.query(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, page_size, (page - 1) * page_size),
        )
        total = db.query_one("SELECT COUNT(*) AS c FROM orders WHERE user_id=?", (user_id,))["c"]
    else:
        rows = db.query(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
        )
        total = db.query_one("SELECT COUNT(*) AS c FROM orders")["c"]
    return {"code": 0, "message": "ok", "data": {"total": total, "items": rows}}


@router.get("/{oid}")
def get_order(oid: int, _: dict = Depends(get_current_user)):
    row = db.query_one("SELECT * FROM orders WHERE id=?", (oid,))
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"code": 0, "message": "ok", "data": row}


@router.put("/{oid}/status")
def update_status(oid: int, req: OrderStatusReq, _: dict = Depends(get_current_user)):
    row = db.query_one("SELECT * FROM orders WHERE id=?", (oid,))
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    # 已取消/已支付的订单不允许再改状态，模拟真实业务约束
    if row["status"] != "pending":
        return {"code": 1004, "message": "订单状态不可变更", "data": {"status": row["status"]}}
    db.execute("UPDATE orders SET status=? WHERE id=?", (req.status, oid))
    return {"code": 0, "message": "ok", "data": {"order_id": oid, "status": req.status}}
