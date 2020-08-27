import uuid
from datetime import datetime
from django import db
from django.db.models import Max
from munigeo.importer.sync import ModelSyncher

from services.management.commands.services_import.services import (
    update_service_root_service_nodes,
)
from services.models import Service, ServiceNode
from smbackend_turku.importers.services import UTC_TIMEZONE
from smbackend_turku.importers.utils import get_ptv_resource
from smbackend_turku.models import ServicePTVIdentifier

PTV_NODE_MAPPING = {
    "Aikuis- ja täydennyskoulutus": "Aikuiskoulutus",
    "Elinkeinot": "Työ- ja yrityspalvelut",
    "Erikoissairaanhoito": "Erikoissairaanhoidon palvelut",
    "Kiinteistöt": "Kaavoitus, kiinteistöt ja rakentaminen",
    "Kirjastot ja tietopalvelut": "Aineisto- ja tietopalvelut",
    "Korkeakoulutus": "Ammattikorkeakoulut ja yliopistot",
    "Koulu- ja opiskelijaterveydenhuolto": "Koulu- ja opiskeluterveydenhuolto",
    "Koulutus": "Päivähoito ja koulutus",
    "Kuntoutus": "Kuntoutumispalvelut",
    "Lasten päivähoito": "Päivähoito ja esiopetus",
    "Liikunta ja urheilu": "Liikunta ja ulkoilu",
    "Neuvolapalvelut": "Neuvolat",
    "Oikeusturva": "Oikeudelliset palvelut",
    "Päihde- ja mielenterveyspalvelut": "Mielenterveys- ja päihdepalvelut",
    "Perusterveydenhuolto": "Terveyspalvelut",
    "Rakentaminen": "Kaavoitus, kiinteistöt ja rakentaminen",
    "Retkeily": "Leirialueet ja saaret",
    "Rokotukset": "Koulu- ja opiskeluterveydenhuolto",
    "Suun ja hampaiden terveydenhuolto": "Suun terveydenhuolto",
    "Terveydenhuolto, sairaanhoito ja ravitsemus": "Terveysaseman palvelut",
    "Toimitilat": "Tontit ja toimitilat",
    "Toisen asteen ammatillinen koulutus": "Ammatillinen koulutus",
    "Työ ja työttömyys": "Työllisyyspalvelut",
    "Vammaisten muut kuin asumis- ja kotipalvelut": "Vanhus- ja vammaispalvelut",
    "Vanhusten palvelut": "Vanhus- ja vammaispalvelut",
    "Vapaa-ajan palvelut": "Vapaa-aika",
}


class PTVServiceImporter:
    service_syncher = ModelSyncher(
        Service.objects.filter(ptv_id__isnull=False), lambda obj: obj.id
    )
    service_id_syncher = ModelSyncher(
        ServicePTVIdentifier.objects.all(), lambda obj: obj.id
    )

    def __init__(self, area_code, logger=None):
        self.are_code = area_code
        self.logger = logger

    @db.transaction.atomic
    def import_services(self):
        self._import_services()

    def _import_services(self):
        data = get_ptv_resource(self.are_code, "service")
        id_counter = 1
        for service in data["itemList"]:
            self._handle_service(service, id_counter)
            id_counter += 1

    def _handle_service(self, service_data, id_counter):
        uuid_id = uuid.UUID(service_data.get("id"))
        id_obj = self.service_id_syncher.get(uuid_id)
        # Only import services related to the imported units, therefore their ids should be found.
        if not id_obj:
            return

        if id_obj.service:
            service_id = id_obj.service.id
        else:
            # Create an id by getting next available id since AutoField is not in use.
            service_id = (
                Service.objects.aggregate(Max("id"))["id__max"] or 0
            ) + id_counter

        service_obj = self.service_syncher.get(service_id)
        if not service_obj:
            service_obj = Service(
                id=service_id, clarification_enabled=False, period_enabled=False
            )
            service_obj._changed = True

        if not id_obj.service:
            id_obj.service = service_obj
            id_obj._changed = True
            self._save_object(id_obj)

        self._handle_service_names(service_data, service_obj)
        self._save_object(service_obj)
        self._handle_service_nodes(service_data, service_obj)

    def _handle_service_names(self, service_data, service_obj):
        for name in service_data.get("serviceNames"):
            lang = name.get("language")
            value = name.get("value")
            obj_key = "{}_{}".format("name", lang)
            setattr(service_obj, obj_key, value)

    def _handle_service_nodes(self, service_data, service_obj):
        for service_class in service_data.get("serviceClasses"):
            self._handle_service_node(service_class, service_obj)
        update_service_root_service_nodes()

    def _handle_service_node(self, node, service_obj):
        for name in node.get("name"):
            if name.get("language") == "fi":
                value = name.get("value")
                if value in PTV_NODE_MAPPING:
                    value = PTV_NODE_MAPPING.get(value)

                node_obj = ServiceNode.objects.filter(name=value).first()
                if not node_obj:
                    # TODO: Negotiate what to do with the nodes that can't be mapped to the existing ones.
                    self.logger.warning(
                        'ServiceNode "{}" does not exist!'.format(value)
                    )
                    break

                node_obj.related_services.add(service_obj)
                node_obj._changed = True
                self._save_object(node_obj)

    def _save_object(self, obj):
        if obj._changed:
            obj.last_modified_time = datetime.now(UTC_TIMEZONE)
            obj.save()
