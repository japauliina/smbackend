# Generated by Django 2.2.13 on 2020-09-02 10:52

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0077_unit_soft_delete"),
        ("ptv", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServicePTVIdentifier",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False)),
                (
                    "service",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ptv_id",
                        to="services.Service",
                    ),
                ),
            ],
        ),
    ]
