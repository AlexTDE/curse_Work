from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('testsystem', '0003_run'),
    ]

    operations = [
        migrations.AddField(
            model_name='run',
            name='ci_job_id',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='run',
            name='coverage',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='run',
            name='error_message',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='run',
            name='reference_diff_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='run',
            name='task_tracker_issue',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AlterField(
            model_name='run',
            name='status',
            field=models.CharField(choices=[('queued', 'Queued'), ('processing', 'Processing'), ('finished', 'Finished'), ('failed', 'Failed')], default='queued', max_length=32),
        ),
        migrations.CreateModel(
            name='CoverageMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_elements', models.PositiveIntegerField(default=0)),
                ('matched_elements', models.PositiveIntegerField(default=0)),
                ('mismatched_elements', models.PositiveIntegerField(default=0)),
                ('coverage_percent', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('run', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='coverage_metric', to='testsystem.run')),
            ],
        ),
        migrations.CreateModel(
            name='Defect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField()),
                ('severity', models.CharField(choices=[('minor', 'Minor'), ('major', 'Major'), ('critical', 'Critical')], default='minor', max_length=16)),
                ('screenshot', models.ImageField(blank=True, null=True, upload_to='defects/')),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('element', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='defects', to='testsystem.uielement')),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='defects', to='testsystem.run')),
                ('testcase', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='defects', to='testsystem.testcase')),
            ],
        ),
    ]



