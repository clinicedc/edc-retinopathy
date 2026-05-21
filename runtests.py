#!/usr/bin/env python
"""Run tests for edc-retinopathy."""

import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def main() -> None:
    if not settings.configured:
        settings.DJANGO_SETTINGS_MODULE = "edc_retinopathy.tests.settings"
        django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["edc_retinopathy.tests"])
    sys.exit(bool(failures))


if __name__ == "__main__":
    main()
