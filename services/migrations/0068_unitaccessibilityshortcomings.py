# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-04-30 09:27
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0067_unit_extensions'),
    ]

    operations = [
        migrations.CreateModel(
            name='UnitAccessibilityShortcomings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accessibility_shortcoming_count', django.contrib.postgres.fields.jsonb.JSONField(default='{}', null=True)),
                ('accessibility_description', django.contrib.postgres.fields.jsonb.JSONField(default='{}', null=True)),
                ('unit', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='accessibility_shortcomings', to='services.Unit')),
            ],
        ),
    ]