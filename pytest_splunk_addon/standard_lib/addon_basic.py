import logging

import pytest
from flaky import flaky


class Basic:
    logger = logging.getLogger()

    @pytest.mark.splunk_addon_internal_errors
    def test_splunk_internal_errors(self, splunk_search_util):
        search = "search index=_internal CASE(ERROR) sourcetype!=splunkd_ui_access AND sourcetype!=splunk_web_access AND sourcetype!=splunk_web_service AND sourcetype!=splunkd_access AND sourcetype!=splunkd| dedup sourcetype| table sourcetype"

        result = splunk_search_util.checkQueryCountIsGreaterThanZero(
            search, interval=1, retries=1
        )

        assert result == False

    # This test ensures the contained samples will produce at lease one event per sourcetype
    @pytest.mark.splunk_addon_searchtime
    def test_basic_props(self, splunk_search_util, splunk_app_props):
        search = f"search (index=_internal OR index=*) AND {splunk_app_props['field']}=\"{splunk_app_props['value']}\""

        # run search
        result = splunk_search_util.checkQueryCountIsGreaterThanZero(
            search, interval=1, retries=1
        )

        if not result:
            return [
                f"Search for {splunk_app_props['field']} {splunk_app_props['value']}"
                f"        {search}"
            ]

    # # This test ensures the contained samples will produce at lease one event per eventtype
    # @pytest.mark.splunk_addon_searchtime
    # @flaky(max_runs=5, min_passes=1)
    # def test_basic_eventtype(self, splunk_search_util, eventtypes):
    #
    #     self.logger.debug("Testing eventtype={}", eventtypes)
    #     search = "search (index=_internal OR index=*) AND eventtype=\"{}\"".format(eventtypes)
    #
    #     # run search
    #     result = splunk_search_util.checkQueryCountIsGreaterThanZero(
    #         search,
    #         interval=1, retries=1)
    #
    #     if not result:
    #         pytest.fail(search)
    #
    # @pytest.mark.splunk_addon_searchtime
    # @flaky(max_runs=5, min_passes=1)
    # def test_fields(self, splunk_search_util, prop_elements):
    #     search = "search (index=_internal OR index=*) AND sourcetype=\"{}\" AND {}".format(
    #         prop_elements['sourcetype'],
    #         prop_elements['field']
    #     )
    #
    #     # run search
    #     result = splunk_search_util.checkQueryCountIsGreaterThanZero(
    #         search,
    #         interval=2, retries=5)
    #
    #     if not result:
    #         pytest.fail(search)
