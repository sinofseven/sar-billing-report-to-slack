from datetime import date

import pytest
from freezegun import freeze_time

from report_creator import get_daily_range


class TestGetDailyRange(object):
    @pytest.mark.parametrize(
        "current_date, expected",
        [
            ("2019/06/06 02:34:23.541000+00:00", (date(2019, 6, 5), date(2019, 6, 6))),
            ("2019/03/01 02:34:23.541000+00:00", (date(2019, 2, 28), date(2019, 3, 1))),
            ("2019/03/02 02:34:23.541000+00:00", (date(2019, 3, 1), date(2019, 3, 2))),
        ],
    )
    def test_normal(self, current_date, expected):
        with freeze_time(current_date):
            actual = get_daily_range()
            assert actual == expected
