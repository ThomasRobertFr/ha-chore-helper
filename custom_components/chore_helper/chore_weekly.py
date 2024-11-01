"""Entity for a weekly chore."""

from __future__ import annotations

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import WEEKDAYS

from . import const
from .chore import Chore


class WeeklyChore(Chore):
    """Chore every n weeks, odd weeks or even weeks."""

    __slots__ = "_chore_day", "_first_week", "_period"

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Read parameters specific for Weekly Chore Frequency."""
        super().__init__(config_entry)
        config = config_entry.options
        self._chore_day = config.get(const.CONF_CHORE_DAY, None)
        self._period: int
        self._first_week: int
        config.get(const.CONF_FREQUENCY)
        self._period = config.get(const.CONF_PERIOD, 1)
        self._first_week = config.get(const.CONF_FIRST_WEEK, 1)

    def _add_period_offset(self, start_date: date) -> date:
        return start_date + relativedelta(weeks=self._period, days=-3)

    def _calculate_schedule_start_date(self) -> date:
        """Calculate start date for scheduling offsets."""
        # Smatter version of the next scheduled date, rounding to closest
        # `chore_day` that puts us at around `period` weeks of last completion

        after = self._frequency[:6] == "after-"
        start_date = self._start_date

        if after and self.last_completed is not None:
            # Last complete + 7 * period days
            last_complete = self.last_completed.date()

            # If we did it late in the week (eg sunday instead of saturday)
            chore_weekday = WEEKDAYS.index(self._chore_day)

            # Find the shortest way to get back on scheduled day:
            #
            # If we did it late by 3 days max (eg sunday instead of saturday)
            # cancel the delay and get back to normal schedule
            #      ex          6         - 5 = 1 -> -1
            if 0 < last_complete.weekday() - chore_weekday <= 3:
                delta = - (last_complete.weekday() - chore_weekday)
            # If we did it late by 3 days max the week after (eg monday instead of saturday)
            # cancel the delay and get back to normal schedule
            #      ex          0           + 7 - 5 = 7 - 5 = 2 -> -2
            elif 0 < last_complete.weekday() + 7 - chore_weekday <= 3:
                delta = - (last_complete.weekday() + 7 - chore_weekday)
            # If we did it early by 3 days max (eg monday instead of tuesday)
            # cancel the delay and get back to normal schedule
            #                   0            -   1 = -1 -> +1
            elif -3 <= last_complete.weekday() - chore_weekday < 0:
                delta = - (last_complete.weekday() - chore_weekday)
            # If we did it early by 3 days max the week before (eg sunday instead of tuesday)
            # cancel the delay and get back to normal schedule
            #                   6 - 7          -   1 = -2 -> +2
            elif -3 <= last_complete.weekday() - 7 - chore_weekday < 0:
                delta = - (last_complete.weekday() - 7 - chore_weekday)
            # Otherwise we did it the proper day :D
            else:
                delta = 0

            # Shift last_complete so that adding the period offset puts us on
            # the closest date in 7 * period days falling on the right weekday
            last_complete = last_complete - timedelta(days=delta)

            earliest_date = self._add_period_offset(last_complete)

            if earliest_date > start_date:
                start_date = earliest_date

        return start_date


    def _find_candidate_date(self, day1: date) -> date | None:
        """Calculate possible date, for weekly frequency."""
        start_date = self._calculate_schedule_start_date()
        start_week = start_date.isocalendar()[1]
        day1 = self.calculate_day1(day1, start_date)
        week = day1.isocalendar()[1]
        weekday = day1.weekday()
        offset = -1
        if self._chore_day is not None:
            day_index = WEEKDAYS.index(self._chore_day)
        else:  # if chore day is not set, just repeat the start date's day
            day_index = start_date.weekday()

        if (week - start_week) % self._period == 0:  # Chore this week
            if day_index >= weekday:  # Chore still did not happen
                offset = day_index - weekday
        iterate_by_week = 7 - weekday + day_index
        while offset == -1:  # look in following weeks
            candidate = day1 + relativedelta(days=iterate_by_week)
            week = candidate.isocalendar()[1]
            if (week - start_week) % self._period == 0:
                offset = iterate_by_week
                break
            iterate_by_week += 7
        return day1 + relativedelta(days=offset)
