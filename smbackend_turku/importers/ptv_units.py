import uuid
from datetime import datetime
from django import db
from django.contrib.gis.geos import Point
from django.db.models import Max
from munigeo.importer.sync import ModelSyncher

from services.models import Unit, UnitConnection
from smbackend_turku.importers.units import (
    get_municipality,
    PHONE_OR_EMAIL_SECTION_TYPE,
    UTC_TIMEZONE,
)
from smbackend_turku.importers.utils import get_ptv_resource, handle_ptv_id
from smbackend_turku.models import UnitPTVIdentifier


class UnitPTVImporter:
    unit_syncher = ModelSyncher(
        Unit.objects.filter(ptv_id__isnull=False), lambda obj: obj.id
    )
    unit_id_syncher = ModelSyncher(UnitPTVIdentifier.objects.all(), lambda obj: obj.id)

    def __init__(self, area_code, logger=None):
        self.are_code = area_code
        self.logger = logger

    @db.transaction.atomic
    def import_units(self):
        data = get_ptv_resource(self.are_code)
        id_counter = 1
        for item in data["itemList"]:
            # Import only the channels that have a location
            if item["serviceChannelType"] == "ServiceLocation":
                self._handle_unit(item, id_counter)
                id_counter += 1

    def _handle_unit(self, unit_data, id_counter):
        uuid_id = uuid.UUID(unit_data["id"])

        ptv_id_obj = self.unit_id_syncher.get(uuid_id)
        if not ptv_id_obj:
            ptv_id_obj = UnitPTVIdentifier(id=uuid_id)
            ptv_id_obj._changed = True

        if ptv_id_obj.unit:
            unit_id = ptv_id_obj.unit.id
        else:
            # Create an id by getting next available id since AutoField is not in use.
            unit_id = (Unit.objects.aggregate(Max("id"))["id__max"] or 0) + id_counter

        unit_obj = self.unit_syncher.get(unit_id)
        if not unit_obj:
            unit_obj = Unit(id=unit_id)
            unit_obj._changed = True
            ptv_id_obj.unit = unit_obj
            self._save_object(ptv_id_obj)

        self._handle_fields(unit_obj, unit_data)
        self._save_object(unit_obj)
        self.unit_syncher.mark(unit_obj)

    def _handle_fields(self, unit_obj, unit_data):
        self._handle_name_and_description(unit_obj, unit_data)
        self._handle_location(unit_obj, unit_data)
        self._handle_extra_info(unit_obj, unit_data)
        self._save_object(unit_obj)
        self._handle_ptv_id(unit_obj, unit_data)
        self._handle_opening_hours(unit_obj, unit_data)  # TODO
        self._handle_email_and_phone_numbers(unit_obj, unit_data)
        unit_obj.data_source = "PTV"

    def _handle_name_and_description(self, unit_obj, unit_data):
        for name in unit_data["serviceChannelNames"]:
            self._handle_translation(unit_obj, name, "name")

        for description in unit_data["serviceChannelDescriptions"]:
            self._handle_translation(unit_obj, description, "description")

    def _handle_location(self, unit_obj, unit_data):
        if unit_data["addresses"]:
            addresses = unit_data["addresses"][0].get("streetAddress")

            # Coordinates
            latitude = addresses["latitude"]
            longitude = addresses["longitude"]
            if latitude and longitude:
                point = Point(float(longitude), float(latitude))
                unit_obj.location = point

            # Address
            unit_obj.address_zip = addresses["postalCode"]
            for address_data in addresses["street"]:
                street_address = "{} {}".format(
                    address_data.get("value"), addresses["streetNumber"]
                )
                self._handle_translation(
                    unit_obj, address_data, "street_address", street_address
                )

                post_office = addresses["postOffice"][0]["value"]
                for po in addresses["postOffice"]:
                    if po["language"] == address_data.get("language"):
                        post_office = po["value"]

                address_postal_full = "{} {} {}".format(
                    street_address, unit_obj.address_zip, post_office
                )
                self._handle_translation(
                    unit_obj, address_data, "address_postal_full", address_postal_full
                )

            # Municipality
            municipality_name = next(
                item.get("value")
                for item in addresses["municipality"].get("name")
                if item["language"] == "fi"
            )
            municipality = get_municipality(municipality_name)
            unit_obj.municipality = municipality

    def _handle_extra_info(self, unit_obj, unit_data):
        emails = unit_data["emails"]
        if emails:
            unit_obj.email = emails[0].get("value")

        for web_page in unit_data["webPages"]:
            value = web_page.get("url")
            self._handle_translation(unit_obj, web_page, "www", value)

    def _handle_ptv_id(self, unit_obj, unit_data):
        ptv_id = unit_data.get("id")
        handle_ptv_id(unit_obj, ptv_id)

    def _handle_opening_hours(self, obj, unit_data):
        # TODO
        pass

    def _handle_email_and_phone_numbers(self, unit_obj, unit_data):
        UnitConnection.objects.filter(
            unit=unit_obj, section_type=PHONE_OR_EMAIL_SECTION_TYPE
        ).delete()
        index = 0
        emails = unit_data["emails"]
        if emails:
            email = emails[0].get("value")
            if email:
                UnitConnection.objects.get_or_create(
                    unit=unit_obj,
                    section_type=PHONE_OR_EMAIL_SECTION_TYPE,
                    email=email,
                    name_fi="Sähköposti",
                    name_sv="E-post",
                    name_en="Email",
                    order=index,
                )
                index += 1

        numbers = unit_data["phoneNumbers"]
        if numbers:
            num = numbers[0].get("prefixNumber") + numbers[0].get("number")
            names = {}
            for number in numbers:
                lang = number.get("language")
                if lang:
                    name = number.get("additionalInformation")
                    obj_key = "{}_{}".format("name", lang)
                    names[obj_key] = name

            UnitConnection.objects.get_or_create(
                unit=unit_obj,
                section_type=PHONE_OR_EMAIL_SECTION_TYPE,
                phone=num,
                order=index,
                **names
            )
            index += 1

    def _handle_translation(self, obj, data, field_name, value=None):
        lang = data.get("language")
        if not value:
            value = data.get("value")
        obj_key = "{}_{}".format(field_name, lang)
        setattr(obj, obj_key, value)

    def _save_object(self, obj):
        if obj._changed:
            obj.last_modified_time = datetime.now(UTC_TIMEZONE)
            obj.save()
