from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import CoverageMetric, Run, TestCase as UITestCase


class CoverageMetricModelTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username='tester')
        self.testcase = UITestCase.objects.create(
            title='Landing page',
            description='Smoke test',
            created_by=self.user,
            reference_screenshot=SimpleUploadedFile('ref.png', b'fake', content_type='image/png'),
        )

    def test_string_representation(self):
        run = Run.objects.create(testcase=self.testcase, started_by=self.user)
        metric = CoverageMetric.objects.create(
            run=run,
            total_elements=10,
            matched_elements=8,
            mismatched_elements=2,
            coverage_percent=80.0,
        )
        self.assertIn('80.00', str(metric))
