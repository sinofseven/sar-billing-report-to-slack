import json
import os
import urllib.request
from datetime import date, timedelta
from decimal import Decimal
from traceback import format_exc
from typing import Optional, Tuple

from botocore.client import BaseClient

from tools.aws_tools import get_ce_client


def main(arg_ce_client: Optional[BaseClient] = None):
    ce = get_ce_client() if arg_ce_client is None else arg_ce_client
    result = {"daily": None, "monthly": None, "premonth": None}

    for key, date_range in {
        "daily": get_daily_range(),
        "monthly": get_current_month_range(),
        "premonth": get_pre_month_range(),
    }.items():
        try:
            result[key] = {"isSuccess": True, "data": get_cost(ce, date_range)}
        except Exception as e:
            result[key] = {
                "isSuccess": False,
                "error": {"message": str(e), "stacktrace": format_exc()},
            }
    message = create_message(result)
    if message:
        post_to_slack(message)
    return result


def get_current_month_range() -> Tuple[date, date]:
    today = date.today()
    end_datetime = today
    start_datetime = (
        today.replace(day=1)
        if today.day > 1
        else (today - timedelta(days=1)).replace(day=1)
    )
    return start_datetime, end_datetime


def get_pre_month_range() -> Tuple[date, date]:
    end_date, _ = get_current_month_range()
    start_date = (end_date - timedelta(days=1)).replace(day=1)
    return start_date, end_date


def get_daily_range() -> Tuple[date, date]:
    end_date = date.today()
    start_date = end_date - timedelta(days=1)
    return start_date, end_date


def create_option(date_range: Tuple[date, date]) -> dict:
    return {
        "TimePeriod": {
            "Start": date_range[0].isoformat(),
            "End": date_range[1].isoformat(),
        },
        "Granularity": "MONTHLY",
        "Metrics": ["AmortizedCost"],
    }


def execute_get_cost(option: dict, ce: BaseClient) -> dict:
    resp = ce.get_cost_and_usage(**option)
    return {
        "start": resp["ResultsByTime"][0]["TimePeriod"]["Start"],
        "end": resp["ResultsByTime"][0]["TimePeriod"]["End"],
        "billing": resp["ResultsByTime"][0]["Total"]["AmortizedCost"]["Amount"],
        "unit": resp["ResultsByTime"][0]["Total"]["AmortizedCost"]["Unit"],
    }


def get_cost(client: BaseClient, range: Tuple[date, date]):
    option = create_option(range)
    return execute_get_cost(option, client)


def create_message(data: dict) -> str:
    message_account = None
    message_premonth = None
    message_daily = None
    message_monthly = None

    premonth = None
    month = None
    daily = None
    account_name = os.getenv("ACCOUNT_NAME")
    if account_name:
        message_account = f"アカウント: {account_name}"
    if data["premonth"]["isSuccess"]:
        message_premonth = "先月: {0} {1} ({2}〜{3})".format(
            data["premonth"]["data"]["billing"],
            data["premonth"]["data"]["unit"],
            data["premonth"]["data"]["start"],
            data["premonth"]["data"]["end"],
        )
        premonth = Decimal(data["premonth"]["data"]["billing"])
    if data["monthly"]["isSuccess"]:
        message_monthly = "今月: {0} {1} ({2}〜{3})".format(
            data["monthly"]["data"]["billing"],
            data["monthly"]["data"]["unit"],
            data["monthly"]["data"]["start"],
            data["monthly"]["data"]["end"],
        )
        month = Decimal(data["monthly"]["data"]["billing"])
        if premonth:
            rate = int((month / premonth) * 10000) / 100
            message_monthly += f" (先月比: {rate}%)"
    if data["daily"]["isSuccess"]:
        message_daily = "昨日: {0} {1} ({2}〜{3})".format(
            data["daily"]["data"]["billing"],
            data["daily"]["data"]["unit"],
            data["daily"]["data"]["start"],
            data["daily"]["data"]["end"],
        )
        daily = Decimal(data["daily"]["data"]["billing"])
        if month:
            rate = int((daily / month) * 10000) / 100
            message_daily += f" (今月中比: {rate}%)"
        if premonth:
            rate = int((daily / premonth) * 10000) / 100
            message_daily += f" (先月中比: {rate}%)"
    message = "\n".join(
        [
            x
            for x in ['<!channel>', message_account, message_monthly, message_premonth, message_daily]
            if x
        ]
    )
    return message


def post_to_slack(message: str):
    url = os.environ["SLACK_INCOMMING_WEBHOOK_URL"]
    data = {"text": message}
    req = urllib.request.Request(
        url,
        json.dumps(data, ensure_ascii=False).encode(),
        {"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    return resp
