import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

import app.services.data_fetcher as data_fetcher
import app.services.scheduler as scheduler
import app.services.stock_catalog as stock_catalog
from app.db.session import Base
from app.main import app
from app.models.data_source import DataScheduledTaskConfig


def test_list_default_providers() -> None:
    with TestClient(app) as client:
        response = client.get("/api/data/providers")

    assert response.status_code == 200
    payload = response.json()
    keys = {item["key"] for item in payload["items"]}
    assert "eastmoney_push2his" in keys
    assert "sina_kline" in keys
    assert "tencent_quote" in keys


def test_update_provider_and_credentials() -> None:
    with TestClient(app) as client:
        updated = client.patch(
            "/api/data/providers/iwencai",
            json={
                "enabled": True,
                "test_url": "https://openapi.iwencai.com/ping",
                "cache_ttl_seconds": 1800,
            },
        )
        credential = client.post(
            "/api/data/providers/iwencai/credentials",
            json={"credential_type": "api_key", "value": "secret-token-123"},
        )
        credentials = client.get("/api/data/providers/iwencai/credentials")
        deleted = client.delete("/api/data/providers/iwencai/credentials/api_key")
        reset = client.patch(
            "/api/data/providers/iwencai",
            json={"enabled": False, "test_url": "", "cache_ttl_seconds": 3600},
        )

    assert updated.status_code == 200
    assert updated.json()["enabled"] is True
    assert updated.json()["test_url"] == "https://openapi.iwencai.com/ping"
    assert updated.json()["cache_ttl_seconds"] == 1800

    assert credential.status_code == 200
    assert credential.json()["configured"] is True
    assert credential.json()["masked_value"] == "sec***123"

    assert credentials.status_code == 200
    assert credentials.json()["items"][0]["credential_type"] == "api_key"

    assert deleted.status_code == 200
    assert deleted.json()["items"] == []
    assert reset.status_code == 200


def test_list_default_routes() -> None:
    with TestClient(app) as client:
        response = client.get("/api/data/routes")

    assert response.status_code == 200
    payload = response.json()
    categories = {item["data_category"] for item in payload["items"]}
    assert "daily_kline" in categories
    assert "realtime_quote" in categories


def test_health_check_disabled_provider() -> None:
    with TestClient(app) as client:
        response = client.post("/api/data/health-check", json={"provider_key": "iwencai"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["provider_key"] == "iwencai"
    assert payload["items"][0]["status"] == "disabled"


def test_fetch_realtime_quote(monkeypatch) -> None:
    text = (
        'v_sz300750="51~宁德时代~300750~377.48~374.51~376.00~58048~~~~~'
        '~~~~~~~~~~~~~~~~~~~20260707100954~2.97~0.79~378.88~372.89~~'
        '~~0.14~22.11~~~~~~5.34~~~~~~~";'
    )
    monkeypatch.setattr(data_fetcher, "_http_get_text", lambda *args, **kwargs: text)

    with TestClient(app) as client:
        response = client.get("/api/data/quote/300750")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "300750"
    assert payload["name"] == "宁德时代"
    assert payload["provider_key"] == "tencent_quote"


def test_fetch_daily_klines(monkeypatch) -> None:
    payload = {
        "data": {
            "code": "300750",
            "name": "宁德时代",
            "klines": [
                "2026-07-06,379.23,374.51,381.89,374.05,216480,8167456241.00,2.06,-1.44,-5.49,0.51",
                "2026-07-07,376.00,377.48,378.88,372.89,58048,2180652240.00,1.60,0.79,2.97,0.14",
            ],
        }
    }
    monkeypatch.setattr(data_fetcher, "_http_get_json", lambda *args, **kwargs: payload)

    with TestClient(app) as client:
        response = client.get("/api/data/klines/300750?period=daily&limit=1")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "宁德时代"
    assert len(body["items"]) == 1
    assert body["items"][0]["time"] == "2026-07-07"


def test_fetch_market_news(monkeypatch) -> None:
    payload = {
        "data": {
            "roll_data": [
                {
                    "id": 1,
                    "title": "测试快讯",
                    "brief": "测试内容",
                    "ctime": 1783390057,
                    "level": "C",
                    "stock_list": [{"symbol": "300750"}],
                }
            ]
        }
    }
    monkeypatch.setattr(data_fetcher, "_http_get_json", lambda *args, **kwargs: payload)

    with TestClient(app) as client:
        response = client.get("/api/data/news?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert body["provider_key"] == "cls"
    assert body["items"][0]["title"] == "测试快讯"


def test_watchlist_crud_and_reorder() -> None:
    with TestClient(app) as client:
        created = client.post("/api/data/watchlist", json={"symbol": "688981", "name": "中芯国际"})
        assert created.status_code == 200
        assert created.json()["symbol"] == "688981"

        listed = client.get("/api/data/watchlist")
        assert listed.status_code == 200
        symbols = [item["symbol"] for item in listed.json()["items"]]
        assert "688981" in symbols

        reordered_symbols = ["688981"] + [symbol for symbol in symbols if symbol != "688981"]
        reordered = client.post("/api/data/watchlist/reorder", json={"symbols": reordered_symbols})
        assert reordered.status_code == 200
        assert reordered.json()["items"][0]["symbol"] == "688981"

        deleted = client.delete("/api/data/watchlist/688981")
        assert deleted.status_code == 200
        assert "688981" not in [item["symbol"] for item in deleted.json()["items"]]


def test_stock_search_and_profile() -> None:
    with TestClient(app) as client:
        search_response = client.get("/api/stocks/search?q=300750")
        profile_response = client.get("/api/stocks/300750/profile")

    assert search_response.status_code == 200
    assert search_response.json()["items"][0]["symbol"] == "300750"
    assert profile_response.status_code == 200
    assert profile_response.json()["name"] == "宁德时代"


def test_stock_search_supports_name_query() -> None:
    with TestClient(app) as client:
        response = client.get("/api/stocks/search?q=英维克")

    assert response.status_code == 200
    assert response.json()["items"][0]["symbol"] == "002837"


def test_stock_catalog_sync_uses_full_market_source_and_searches_name_and_code(monkeypatch) -> None:
    def fake_sina_catalog(_client):
        return [{"symbol": "sh600000", "code": "600000", "name": "浦发银行"}] + [
            {"symbol": f"sh{600000 + index:06d}", "code": f"{600000 + index:06d}", "name": f"测试股票{index}"}
            for index in range(1, 1000)
        ]

    monkeypatch.setattr(
        stock_catalog,
        "_fetch_sina_catalog",
        fake_sina_catalog,
    )

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        count, provider = stock_catalog.sync_stock_catalog(session)
        by_name = stock_catalog.search_stocks(session, "浦发", 5)
        by_code = stock_catalog.search_stocks(session, "600000", 5)
    finally:
        session.close()

    assert (count, provider) == (1000, "sina")
    assert by_name[0].symbol == "600000"
    assert by_code[0].name == "浦发银行"


def test_stock_indicators(monkeypatch) -> None:
    payload = {
        "data": {
            "code": "300750",
            "name": "宁德时代",
            "klines": [
                f"2026-07-{day:02d},{100 + day},{101 + day},{102 + day},{99 + day},{1000 + day},100000,1,1,1,1"
                for day in range(1, 31)
            ],
        }
    }
    monkeypatch.setattr(data_fetcher, "_http_get_json", lambda *args, **kwargs: payload)

    with TestClient(app) as client:
        response = client.get("/api/stocks/300750/indicators?names=ma,macd,rsi,kdj,boll&limit=30")

    assert response.status_code == 200
    body = response.json()
    names = {item["name"] for item in body["items"]}
    assert {"MA5", "DIF", "RSI14", "K", "BOLL_UPPER"}.issubset(names)


def test_stock_announcements(monkeypatch) -> None:
    payload = {
        "data": {
            "list": [
                {
                    "art_code": "AN202607061826751850",
                    "codes": [{"stock_code": "300750", "short_name": "宁德时代"}],
                    "columns": [{"column_name": "其他"}],
                    "display_time": "2026-07-06 19:14:09:703",
                    "title": "宁德时代:H股公告",
                    "title_ch": "宁德时代:H股公告",
                }
            ]
        }
    }
    monkeypatch.setattr(data_fetcher, "_http_get_json", lambda *args, **kwargs: payload)

    with TestClient(app) as client:
        response = client.get("/api/stocks/300750/announcements?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert body["provider_key"] == "eastmoney_announcement"
    assert body["items"][0]["id"] == "AN202607061826751850"
    assert body["items"][0]["title"] == "宁德时代:H股公告"
    assert body["items"][0]["category"] == "其他"


def test_phase_two_data_endpoints(monkeypatch) -> None:
    def fake_json(url, *args, **kwargs):
        if "/api/qt/stock/get" in url:
            return {
                "data": {
                    "f57": "300750",
                    "f58": "宁德时代",
                    "f116": 1706216304519.58,
                    "f162": 2057,
                    "f167": 522,
                    "f173": 5.98,
                }
            }
        if "RPT_DMSK_FN_INCOME" in url:
            return {
                "result": {
                    "data": [
                        {
                            "REPORT_DATE": "2026-03-31 00:00:00",
                            "NOTICE_DATE": "2026-04-16 00:00:00",
                            "TOTAL_OPERATE_INCOME": 129131041000,
                            "PARENT_NETPROFIT": 20737710000,
                        }
                    ]
                }
            }
        if "/api/qt/stock/fflow/kline/get" in url:
            return {
                "data": {
                    "code": "300750",
                    "name": "宁德时代",
                    "klines": ["2026-07-08,-304002048.0,263505776.0,40496256.0,34822000.0,-338824048.0"],
                }
            }
        if "/api/qt/clist/get" in url:
            return {
                "data": {
                    "diff": [
                        {"f12": "BK1207", "f14": "计算机", "f2": 7552.87, "f3": 1.41, "f62": 5195156224.0, "f184": 6.58}
                    ]
                }
            }
        if "RPT_MUTUAL_DEAL_HISTORY" in url:
            return {
                "result": {
                    "data": [
                        {
                            "MUTUAL_TYPE": "001",
                            "TRADE_DATE": "2026-07-07 00:00:00",
                            "DEAL_AMT": 151697.8,
                            "LEAD_STOCKS_CODE": "600120.SH",
                            "LEAD_STOCKS_NAME": "浙江东方",
                        }
                    ]
                }
            }
        if "/report/list" in url:
            return {
                "data": [
                    {
                        "title": "技术发布会简析",
                        "stockName": "宁德时代",
                        "stockCode": "300750",
                        "orgSName": "交银国际证券",
                        "publishDate": "2026-04-23 00:00:00.000",
                        "infoCode": "AP202604231821483907",
                        "emRatingName": "买入",
                    }
                ]
            }
        return {}

    monkeypatch.setattr(data_fetcher, "_http_get_json", fake_json)

    with TestClient(app) as client:
        fundamentals = client.get("/api/stocks/300750/fundamentals")
        statements = client.get("/api/stocks/300750/financial-statements?statement_type=income&limit=1")
        fund_flow = client.get("/api/stocks/300750/fund-flow?limit=1")
        sectors = client.get("/api/sectors/snapshots?sector_type=industry&limit=1")
        northbound = client.get("/api/market/northbound-flow?limit=1")
        reports = client.get("/api/stocks/300750/research-reports?limit=1")

    assert fundamentals.status_code == 200
    assert fundamentals.json()["provider_key"] == "eastmoney_push2"
    assert any(item["key"] == "market_cap" for item in fundamentals.json()["metrics"])

    assert statements.status_code == 200
    assert statements.json()["items"][0]["values"]["PARENT_NETPROFIT"] == 20737710000

    assert fund_flow.status_code == 200
    assert fund_flow.json()["items"][0]["main_net_inflow"] == -304002048.0

    assert sectors.status_code == 200
    assert sectors.json()["items"][0]["name"] == "计算机"

    assert northbound.status_code == 200
    assert northbound.json()["items"][0]["lead_stock_name"] == "浙江东方"

    assert reports.status_code == 200
    assert reports.json()["items"][0]["rating"] == "买入"


def test_phase_three_data_endpoints(monkeypatch) -> None:
    def fake_json(url, *args, **kwargs):
        if "RPT_DAILYBILLBOARD_DETAILS" in url:
            return {
                "result": {
                    "data": [
                        {
                            "TRADE_DATE": "2020-07-07 00:00:00",
                            "SECURITY_CODE": "300750",
                            "SECURITY_NAME_ABBR": "宁德时代",
                            "EXPLANATION": "日涨幅偏离值达到7%",
                            "BILLBOARD_BUY_AMT": 991212330.68,
                            "BILLBOARD_SELL_AMT": 1140115075.33,
                            "BILLBOARD_NET_AMT": -148902744.65,
                        }
                    ]
                }
            }
        if "RPT_LIFT_STAGE" in url:
            return {
                "result": {
                    "data": [
                        {
                            "FREE_DATE": "2024-09-24 00:00:00",
                            "SECURITY_CODE": "300750",
                            "SECURITY_NAME_ABBR": "宁德时代",
                            "FREE_SHARES": 390146.5544,
                            "LIFT_MARKET_CAP": 63369.729288,
                            "FREE_RATIO": 0.000822324064,
                            "FREE_SHARES_TYPE": "股权激励限售股份",
                        }
                    ]
                }
            }
        if "RPTA_WEB_RZRQ_GGMX" in url:
            return {
                "result": {
                    "data": [
                        {
                            "DATE": "2026-07-07 00:00:00",
                            "SCODE": "300750",
                            "SECNAME": "宁德时代",
                            "RZYE": 22983798951,
                            "RQYE": 138220609,
                            "RZRQYE": 23122019560,
                            "RZMRE": 542931750,
                            "RZJME": -10679244,
                            "RQMCL": 14400,
                        }
                    ]
                }
            }
        if "RPT_ECONOMY_CPI" in url:
            return {
                "result": {
                    "data": [
                        {
                            "REPORT_DATE": "2026-05-01 00:00:00",
                            "TIME": "2026年05月份",
                            "NATIONAL_SAME": 1.2,
                        }
                    ]
                }
            }
        return {}

    monkeypatch.setattr(data_fetcher, "_http_get_json", fake_json)

    with TestClient(app) as client:
        dragon = client.get("/api/stocks/300750/dragon-tiger?limit=1")
        lockup = client.get("/api/stocks/300750/lockup-expiry?limit=1")
        margin = client.get("/api/stocks/300750/margin-trading?limit=1")
        macro = client.get("/api/market/macro?indicator=cpi&limit=1")
        quality = client.get("/api/data/quality")
        alerts = client.get("/api/data/alerts?limit=5")

    assert dragon.status_code == 200
    assert dragon.json()["items"][0]["net_amount"] == -148902744.65
    assert lockup.status_code == 200
    assert lockup.json()["items"][0]["share_type"] == "股权激励限售股份"
    assert margin.status_code == 200
    assert margin.json()["items"][0]["financing_balance"] == 22983798951
    assert macro.status_code == 200
    assert macro.json()["items"][0]["values"]["NATIONAL_SAME"] == 1.2
    assert quality.status_code == 200
    assert "items" in quality.json()
    assert alerts.status_code == 200
    assert "items" in alerts.json()


def test_cache_clear() -> None:
    with TestClient(app) as client:
        response = client.post("/api/data/cache/clear")

    assert response.status_code == 200
    assert response.json()["cleared"] is True


def test_scheduled_tasks_list() -> None:
    with TestClient(app) as client:
        response = client.get("/api/data/scheduled-tasks")

    assert response.status_code == 200
    payload = response.json()
    keys = {item["key"] for item in payload["items"]}
    assert "data_source_health_check" in keys
    assert "watchlist_quote_refresh" in keys
    assert "market_news_refresh" in keys


def test_scheduled_task_manual_run_and_logs() -> None:
    task_key = "test_noop_task"
    scheduler.TASKS[task_key] = scheduler.ScheduledTask(
        key=task_key,
        name="Test noop task",
        description="Test task",
        interval_seconds=3600,
        enabled=True,
        runner=lambda db: "ok",
    )
    try:
        with TestClient(app) as client:
            run_response = client.post(f"/api/data/scheduled-tasks/{task_key}/run")
            logs_response = client.get("/api/data/scheduled-task-runs?limit=5")
    finally:
        scheduler.TASKS.pop(task_key, None)

    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["task_key"] == task_key
    assert run_payload["status"] == "success"
    assert run_payload["message"] == "ok"

    assert logs_response.status_code == 200
    logs = logs_response.json()["items"]
    assert any(item["task_key"] == task_key for item in logs)


def test_premarket_analysis_persists_ranked_watchlist_candidates(monkeypatch) -> None:
    def fake_klines(db, symbol: str, period: str, limit: int):
        base = 80 + int(symbol[-2:]) / 10
        bars = [SimpleNamespace(close=base + index * 0.5, volume=1000 + index * 30) for index in range(30)]
        return SimpleNamespace(name=f"测试{symbol}", items=bars)

    monkeypatch.setattr(scheduler, "get_klines", fake_klines)

    with TestClient(app) as client:
        run = client.post("/api/data/scheduled-tasks/premarket_watchlist_analysis/run")
        result = client.get("/api/data/premarket-recommendations")
        tasks = client.get("/api/data/scheduled-tasks")

    assert run.status_code == 200
    assert run.json()["status"] == "success"
    assert result.status_code == 200
    assert result.json()["source_label"] == "当前自选股候选池"
    assert result.json()["items"]
    assert result.json()["items"][0]["rank"] == 1
    assert result.json()["items"] == sorted(result.json()["items"], key=lambda item: item["score"], reverse=True)
    premarket_task = next(item for item in tasks.json()["items"] if item["key"] == "premarket_watchlist_analysis")
    assert premarket_task["schedule"] == "交易日 08:30"
    assert premarket_task["category"] == "analysis"


def test_scheduled_task_schedule_can_be_updated() -> None:
    task_key = "premarket_watchlist_analysis"
    with scheduler.SessionLocal() as db:
        existing = db.get(DataScheduledTaskConfig, task_key)
        previous = (existing.enabled, existing.daily_time) if existing else None
    try:
        with TestClient(app) as client:
            updated = client.patch(
                f"/api/data/scheduled-tasks/{task_key}",
                json={"enabled": False, "daily_time": "07:45"},
            )
            listed = client.get("/api/data/scheduled-tasks")

        assert updated.status_code == 200
        assert updated.json()["enabled"] is False
        assert updated.json()["daily_time"] == "07:45"
        assert updated.json()["schedule"] == "交易日 07:45"
        item = next(row for row in listed.json()["items"] if row["key"] == task_key)
        assert item["enabled"] is False
        assert item["daily_time"] == "07:45"
    finally:
        with scheduler.SessionLocal() as db:
            db.execute(delete(DataScheduledTaskConfig).where(DataScheduledTaskConfig.task_key == task_key))
            if previous:
                db.add(DataScheduledTaskConfig(task_key=task_key, enabled=previous[0], daily_time=previous[1]))
            db.commit()


def test_market_news_alias(monkeypatch) -> None:
    payload = {
        "data": {
            "roll_data": [
                {
                    "id": 2,
                    "title": "市场快讯",
                    "brief": "测试市场新闻",
                    "ctime": 1783390057,
                    "level": "C",
                    "stock_list": [],
                }
            ]
        }
    }
    monkeypatch.setattr(data_fetcher, "_http_get_json", lambda *args, **kwargs: payload)

    with TestClient(app) as client:
        response = client.get("/api/market/news?limit=1")

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "市场快讯"


def test_data_snapshot(monkeypatch) -> None:
    kline_payload = {
        "data": {
            "code": "300750",
            "name": "宁德时代",
            "klines": [
                f"2026-07-{day:02d},{100 + day},{101 + day},{102 + day},{99 + day},{1000 + day},100000,1,1,1,1"
                for day in range(1, 31)
            ],
        }
    }
    news_payload = {"data": {"roll_data": []}}

    def fake_json(url, *args, **kwargs):
        if "api/cache" in url:
            return news_payload
        return kline_payload

    monkeypatch.setattr(data_fetcher, "_http_get_json", fake_json)
    monkeypatch.setattr(
        data_fetcher,
        "_http_get_text",
        lambda *args, **kwargs: 'v_sz300750="51~宁德时代~300750~377.48~374.51~376.00~58048~~~~~~~~~~~~~~~~~~~~20260707100954~2.97~0.79~378.88~372.89~~~0.14~22.11~~~~~~5.34~~~~~~~";',
    )

    with TestClient(app) as client:
        created = client.post("/api/data/snapshots", json={"symbol": "300750", "limit": 30})
        detail = client.get(f"/api/data/snapshots/{created.json()['id']}")
        missing = client.get("/api/data/snapshots/999999999")
        listed = client.get("/api/data/snapshots?symbol=300750")

    assert created.status_code == 200
    assert created.json()["symbol"] == "300750"
    assert detail.status_code == 200
    assert detail.json()["id"] == created.json()["id"]
    assert json.loads(detail.json()["snapshot_json"])["symbol"] == "300750"
    assert missing.status_code == 404
    assert listed.status_code == 200
    assert listed.json()["items"]
