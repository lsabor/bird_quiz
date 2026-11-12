import django.db.models.deletion
from django.db import migrations, models


def clear(apps, schema_editor):
    # Old rows were per-trip; they're rebuilt per-region from the cached API/bar chart data.
    apps.get_model("birds", "SpeciesFrequency").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("birds", "0001_initial")]

    operations = [
        migrations.RunPython(clear, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(name="speciesfrequency", unique_together=set()),
        migrations.RemoveField(model_name="speciesfrequency", name="trip_set"),
        migrations.AddField(
            model_name="speciesfrequency",
            name="region",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="frequencies", to="birds.tripregion"
            ),
        ),
        migrations.AlterUniqueTogether(name="speciesfrequency", unique_together={("region", "taxon")}),
    ]
