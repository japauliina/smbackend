import logging

import pytest

from ptv.tests.utils import create_municipality, get_ptv_test_resource
from services.models import Service, Unit


@pytest.mark.django_db
def test_service_import():
    create_municipality()
    logger = logging.getLogger(__name__)

    from ptv.importers.ptv_units import UnitPTVImporter

    unit_importer = UnitPTVImporter(area_code="001")
    data = get_ptv_test_resource()
    unit_importer._import_units(data)

    from ptv.importers.ptv_services import PTVServiceImporter

    service_importer = PTVServiceImporter(area_code="001", logger=logger)
    data = get_ptv_test_resource(resource_name="service")
    service_importer._import_services(data)

    service_1 = Service.objects.get(name="Hammaslääkäri")
    service_2 = Service.objects.get(name="Perusopetus")
    unit_1 = Unit.objects.get(name="Terveysasema")
    unit_2 = Unit.objects.get(name="Peruskoulu")

    assert Service.objects.count() == 2
    assert service_1 in unit_1.services.all()
    assert service_2 in unit_2.services.all()
