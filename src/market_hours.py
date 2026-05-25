from __future__ import annotations

from datetime import datetime, time

import pytz


VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")
MORNING_START = time(9, 0)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)


def now_vn() -> datetime:
    return datetime.now(VN_TZ)


def is_trading_time(moment: datetime | None = None) -> bool:
    current = moment.astimezone(VN_TZ) if moment else now_vn()
    if current.weekday() >= 5:
        return False

    current_time = current.time()
    return (
        MORNING_START <= current_time <= MORNING_END
        or AFTERNOON_START <= current_time <= AFTERNOON_END
    )
