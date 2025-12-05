from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testsystem', '0004_run_enhancements'),
    ]

    operations = [
        migrations.AddField(
            model_name='uielement',
            name='text',
            field=models.CharField(blank=True, max_length=256),
        ),
    ]

