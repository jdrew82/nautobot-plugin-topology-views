# Generated by Django 4.1.8 on 2023-09-25 21:18

from django.db import migrations, models
import django.db.models.deletion
import taggit.managers
import utilities.json


class Migration(migrations.Migration):

    dependencies = [
        ('nautobot_topology_views', '0005_individualoptions_save_coords'),
    ]

    operations = [
        migrations.CreateModel(
            name='PowerPanelCoordinate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('x', models.IntegerField()),
                ('y', models.IntegerField()),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dcim.powerpanel')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='nautobot_topology_views.coordinategroup')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'ordering': ['group', 'device'],
                'unique_together': {('device', 'group')},
            },
        ),
        migrations.CreateModel(
            name='PowerFeedCoordinate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('x', models.IntegerField()),
                ('y', models.IntegerField()),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dcim.powerfeed')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='nautobot_topology_views.coordinategroup')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'ordering': ['group', 'device'],
                'unique_together': {('device', 'group')},
            },
        ),
        migrations.CreateModel(
            name='CircuitCoordinate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('x', models.IntegerField()),
                ('y', models.IntegerField()),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='circuits.circuit')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='nautobot_topology_views.coordinategroup')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'ordering': ['group', 'device'],
                'unique_together': {('device', 'group')},
            },
        ),
    ]
