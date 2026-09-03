import datetime as dt
import unittest

import solar_monitor_guidance as smg


class SolarMonitorGuidanceTests(unittest.TestCase):
    def test_url_requests_the_issue_date_forecast_table(self):
        issued = dt.datetime(2026, 9, 3, 21, tzinfo=smg.UTC)
        self.assertEqual(
            smg.solar_monitor_url(issued),
            "https://www.solarmonitor.org/forecast.php?date=20260903&region=&indexnum=1",
        )

    def test_explicit_no_data_page_is_not_described_as_a_parser_failure(self):
        document = """
        <html><div class="header_sm" id="NOAA-header">
        Active Regions <br> No Data
        </div><table><tr><th>NOAA Number</th></tr></table></html>
        """
        with self.assertRaisesRegex(smg.SolarMonitorError, "explicitly reports no"):
            smg.parse_solar_monitor_html(document)

    def test_current_nested_table_shape(self):
        document = """
        <table><tr><th>NOAA Number</th></tr><tr><td>14518</td></tr></table>
        <table><tr><th>MCEVOL</th><th>MCSTAT</th><th>NOAA</th></tr>
          <tr><td>17</td><td>23</td><td>20</td></tr></table>
        <table><tr><th>MCEVOL</th><th>MCSTAT</th><th>NOAA</th></tr>
          <tr><td>4</td><td>6</td><td>5</td></tr></table>
        <table><tr><th>MCEVOL</th><th>MCSTAT</th><th>NOAA</th></tr>
          <tr><td>1</td><td>2</td><td>1</td></tr></table>
        """
        rows = smg.parse_solar_monitor_html(document)
        self.assertEqual(rows[0]["noaa_region"], 14518)
        self.assertEqual(rows[0]["m1"]["mcevol"], 4.0)
        self.assertEqual(rows[0]["x1"]["mcstat"], 2.0)


if __name__ == "__main__":
    unittest.main()
