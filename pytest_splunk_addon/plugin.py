# -*- coding: utf-8 -*-
"""
Module usage:
- splunk_appinspect: To parse the configuration files from Add-on package
"""

import logging
import re
import pytest
from splunk_appinspect import App
from itertools import product

LOGGER = logging.getLogger("pytest_splunk_addon")


def pytest_configure(config):
    """
    Setup configuration after command-line options are parsed
    """
    config.addinivalue_line("markers", "splunk_addon_internal_errors: Check Errors")
    config.addinivalue_line("markers", "splunk_addon_searchtime: Test search time only")


def dedup_tests(test_list):
    """
    Deduplicate the test case parameters based on param.id
    Args:
        test_list(Generator): Generator of pytest.param
    Yields:
        Generator: De-duplicated pytest.param
    """
    seen_tests = set()
    for each_param in test_list:
        if each_param.id not in seen_tests:
            yield each_param
            seen_tests.add(each_param.id)


def pytest_generate_tests(metafunc):
    """
    Parse the fixture dynamically.
    """
    for fixture in metafunc.fixturenames:
        if fixture.startswith("splunk_app"):
            LOGGER.info("generating testcases for splunk_app. fixture=%s", fixture)
            # Load associated test data
            tests = load_splunk_tests(metafunc.config.getoption("splunk_app"), fixture)
            metafunc.parametrize(fixture, dedup_tests(tests))


def load_splunk_tests(splunk_app_path, fixture):
    """
    Utility function to load the test cases with the App fields

    Args:
        splunk_app_path(string): Path of the Splunk App
        fixture: The list of fixtures

    Yields:
        List of knowledge objects as pytest parameters
    """
    LOGGER.info("Initializing App parsing mechanism.")
    app = App(splunk_app_path, python_analyzer_enable=False)
    if fixture.endswith("props"):
        props = app.props_conf()
        LOGGER.info("Successfully parsed props configurations")
        yield from load_splunk_props(props)
    elif fixture.endswith("fields"):
        props = app.props_conf()
        transforms = app.transforms_conf()
        LOGGER.info("Successfully parsed props configurations")
        yield from load_splunk_fields(props, transforms)
    else:
        yield None


def load_splunk_props(props):
    """
    Parse the props.conf of the App & yield stanzas

    Args:
        props(): The configuration object of props

    Yields:
        generator of stanzas from the props
    """
    for props_section in props.sects:
        if props_section.startswith("host::"):
            LOGGER.info("Skipping host:: stanza=%s", props_section)
            continue
        elif props_section.startswith("source::"):
            LOGGER.info("Skipping source:: stanza=%s", props_section)
            continue
        else:
            LOGGER.info("parsing sourcetype stanza=%s", props_section)
            yield return_props_sourcetype_param(props_section, props_section)


def return_props_sourcetype_param(id, value):
    """
    Convert sourcetype to pytest parameters
    """
    idf = f"sourcetype::{id}"
    LOGGER.info("Generated pytest.param of sourcetype with id=%s", idf)
    return pytest.param({"field": "sourcetype", "value": value}, id=idf)


def load_splunk_fields(props, transforms):
    """
    Parse the App configuration files & yield fields

    Args:
        props(): The configuration object of props
        transforms(): The configuration object of transforms

    Yields:
        generator of fields
    """
    for stanza_name in props.sects:
        section = props.sects[stanza_name]
        if section.name.startswith("source::"):
            stanza_type = "source"
            stanza_list = list(get_list_of_sources(stanza_name))
        else:
            stanza_type = "sourcetype"
            stanza_list = [stanza_name]
        for current in section.options:
            LOGGER.info("Parsing parameter=%s of stanza=%s", current, stanza_name)
            field_data = section.options[current]
            for each_stanza_name in stanza_list:
                # if current.startswith("EXTRACT-"):
                #     yield from return_props_extract(
                #         stanza_type, each_stanza_name, field_data
                #     )
                # elif current.startswith("EVAL-"):
                #     yield return_props_eval(each_stanza_name, field_data, stanza_type)
                if current.startswith("REPORT-"):
                    yield from return_transforms_report(
                        transforms, stanza_type, each_stanza_name, field_data
                    )


def get_params_from_regex(regex, property_value, stanza_type, stanza_name, fields):
    """
    Returns the fields captured using regex as pytest parameters

    Args:
        regex(str): The regular expression used to capture the fields
        property_value(str): The property string on which regex will be applied to extract fields.
        stanza_type(str): stanza type (source/sourcetype)
        stanza_name(str): source/sourcetype name
        fields(list): list of fields preset in a props property.
        
    Yields:
        generator of fields as pytest parameters
    """
    matches = re.finditer(regex, property_value, re.MULTILINE)
    for matchNum, match in enumerate(matches, start=1):
        for groupNum in range(0, len(match.groups())):
            groupNum = groupNum + 1
            field_test_name = "{}::{}".format(stanza_name, match.group(groupNum))
            yield pytest.param(
                {
                    "stanza_type": stanza_type,
                    "stanza_name": stanza_name,
                    "fields": [match.group(groupNum)],
                },
                id=field_test_name,
            )
            fields.append(match.group(groupNum))


def return_transforms_report(transforms, stanza_type, stanza_name, report_property):
    """
    Returns the fields parsed from transforms.conf  as pytest parameters

    Args:
        transforms(): The configuration object of transforms
        stanza_type(str): stanza type (source/sourcetype)
        stanza_name(str): source/sourcetype name
        report_property(splunk_appinspect.configuration_file.ConfigurationSetting): The configuration setting object of REPORT.
            properties used:
                    name : key in the configuration settings
                    value : value of the respective name in the configuration
    Yields:
        generator of fields as pytest parameters
    """
    try:
        for transforms_section in [
            each_stanza.strip() for each_stanza in report_property.value.split(",")
        ]:
            report_test_name = (
                f"{stanza_name}::{report_property.name}::{transforms_section}"
            )
            fields = []
            section = transforms.sects[transforms_section]
            if (
                "SOURCE_KEY" in section.options
                and section.options["SOURCE_KEY"].value != ""
            ):
                yield pytest.param(
                    {
                        "stanza_type": stanza_type,
                        "stanza_name": stanza_name,
                        "fields": [section.options["SOURCE_KEY"].value],
                    },
                    id="{}::{}".format(
                        stanza_name, section.options["SOURCE_KEY"].value
                    ),
                )
                fields.append(section.options["SOURCE_KEY"].value)
            if "REGEX" in section.options and section.options["REGEX"].value != "":
                regex = r"\(\?<([^\>]+)\>"
                yield from get_params_from_regex(
                    regex,
                    section.options["REGEX"].value,
                    stanza_type,
                    stanza_name,
                    fields,
                )
            if "FIELDS" in section.options and section.options["FIELDS"].value != "":
                fields_list = [
                    each_field.strip()
                    for each_field in section.options["FIELDS"].value.split(",")
                ]
                for each_field in fields_list:
                    yield pytest.param(
                        {
                            "stanza_type": stanza_type,
                            "stanza_name": stanza_name,
                            "fields": [each_field],
                        },
                        id="{}::{}".format(stanza_name, each_field),
                    )
                    fields.append(each_field)
            if "FORMAT" in section.options and section.options["FORMAT"].value != "":
                regex = r"(\S*)::"
                yield from get_params_from_regex(
                    regex,
                    section.options["FORMAT"].value,
                    stanza_type,
                    stanza_name,
                    fields,
                )
            yield pytest.param(
                {
                    "stanza_type": stanza_type,
                    "stanza_name": stanza_name,
                    "fields": fields,
                },
                id=report_test_name,
            )
    except KeyError:
        LOGGER.error(
            "The stanza {} doesnot exists in transforms.conf.".format(
                transforms_section
            ),
        )


def return_props_extract(stanza_type, stanza_name, props_property):
    """
    Returns the fields parsed from EXTRACT as pytest parameters

    Args:
        stanza_type(str): stanza type (source/sourcetype)
        stanza_name(str): source/sourcetype name
        props_property(splunk_appinspect.configuration_file.ConfigurationSetting): The configuration setting object of EXTRACT.
            properties used:
                    name : key in the configuration settings
                    value : value of the respective name in the configuration
    Yields:
        generator of fields as pytest parameters
    """
    test_name = f"{stanza_name}::{props_property.name}"
    regex = r"\(\?<([^\>]+)\>(?:.*(?i)in\s+(.*))?"
    matches = re.finditer(regex, props_property.value, re.MULTILINE)
    fields = []
    for match_num, match in enumerate(matches, start=1):
        for group_num in range(0, len(match.groups())):
            group_num = group_num + 1
            if match.group(group_num):
                field_test_name = "{}_field::{}".format(
                    stanza_name, match.group(group_num)
                )
                yield pytest.param(
                    {
                        "stanza_type": stanza_type,
                        "stanza_name": stanza_name,
                        "fields": [match.group(group_num)],
                    },
                    id=field_test_name,
                )
                fields.append(match.group(group_num))
    if fields:
        fields.reverse()
        LOGGER.info(
            "Generated pytest.param for extract. stanza_type=%s stanza_name=%s, fields=%s",
            stanza_type,
            stanza_name,
            str(fields),
        )
        yield pytest.param(
            {"stanza_type": stanza_type, "stanza_name": stanza_name, "fields": fields},
            id=test_name,
        )


def return_props_eval(stanza_name, field_data, stanza_type):
    """
    Return the fields parsed from EVAL as pytest parameters
      
    Args:
        @stanza_name(str): source/sourcetype name
        @field_data(object): Eval field details
        @stanza_type: Stanza type (source/sourcetype)

    Return:
        List of pytest parameters
    """
    name = f"{stanza_type}_{stanza_name}_field::{field_data.name}"
    regex = r"EVAL-(?P<FIELD>.*)"
    fields = re.findall(regex, field_data.name, re.IGNORECASE)

    return pytest.param(
        {"stanza_type": stanza_type, "stanza_name": stanza_name, "fields": fields},
        id=name,
    )


def get_list_of_sources(source):
    """
    Implement generator object of source list
      
    Args:
        @param source(str): Source name
    """
    match_obj = re.search(r"source::(.*)", source)
    value = match_obj.group(1).replace("...", "*")
    sub_groups = re.findall("\([^\)]+\)", value)
    sub_group_list = []
    for each_group in sub_groups:
        sub_group_list.append(list(each_group.strip("()").split("|")))
    template = re.sub(r"\([^\)]+\)", "{}", value)
    for each_permutation in product(*sub_group_list):
        yield template.format(*each_permutation)
