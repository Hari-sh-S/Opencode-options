import streamlit as st
from dhanhq import dhanhq
from datetime import datetime

class OrderManager:
    def __init__(self, dhan):
        self.dhan = dhan

    def place_order(self, security_id, transaction_type, quantity, price=None,
                    order_type="MARKET", product_type="INTRADAY", tag=""):
        try:
            if order_type.upper() == "MARKET":
                resp = self.dhan.place_order(
                    security_id=str(security_id),
                    exchange_segment=dhanhq.NSE_FNO,
                    transaction_type=dhanhq.BUY if transaction_type.upper() == "BUY" else dhanhq.SELL,
                    quantity=quantity,
                    order_type=dhanhq.MARKET,
                    product_type=dhanhq.INTRA if product_type.upper() == "INTRADAY" else dhanhq.MARGIN,
                    tag=tag,
                )
            else:
                resp = self.dhan.place_order(
                    security_id=str(security_id),
                    exchange_segment=dhanhq.NSE_FNO,
                    transaction_type=dhanhq.BUY if transaction_type.upper() == "BUY" else dhanhq.SELL,
                    quantity=quantity,
                    order_type=dhanhq.LIMIT,
                    product_type=dhanhq.INTRA if product_type.upper() == "INTRADAY" else dhanhq.MARGIN,
                    price=price,
                    tag=tag,
                )
            return resp
        except Exception as e:
            st.error(f"Order placement failed: {e}")
            return {"status": "failure", "remarks": str(e)}

    def get_positions(self):
        try:
            return self.dhan.get_positions()
        except Exception:
            return {"status": "failure", "data": []}

    def get_order_list(self):
        try:
            return self.dhan.get_order_list()
        except Exception:
            return {"status": "failure", "data": []}

    def get_fund_limits(self):
        try:
            return self.dhan.get_fund_limits()
        except Exception:
            return {"status": "failure", "data": {}}

    def cancel_order(self, order_id):
        try:
            return self.dhan.cancel_order(order_id=order_id)
        except Exception as e:
            return {"status": "failure", "remarks": str(e)}

    def exit_position(self, security_id, quantity, transaction_type="SELL"):
        return self.place_order(
            security_id=security_id,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type="MARKET",
            tag="EXIT",
        )
