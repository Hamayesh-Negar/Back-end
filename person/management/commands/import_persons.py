import csv
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from conference.models import Conference
from person.models import Person, Task, PersonTask, Category


class Command(BaseCommand):
    help = 'Import persons from CSV file into the Person model'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument('--conference-id', type=int,
                            help='Conference ID to associate with imported persons')
        parser.add_argument('--create-conference', action='store_true',
                            help='Create a new conference if it does not exist')
        parser.add_argument('--category-ids', nargs='+', type=int,
                            help='Category IDs to assign to imported persons (space-separated)')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        conference_id = options.get('conference_id')
        create_conference = options.get('create_conference')
        category_ids = options.get('category_ids', [])

        # Get or create conference
        if not conference_id and not create_conference:
            self.stdout.write(self.style.ERROR(
                'You must specify a conference ID or use --create-conference'))
            return

        conference = None
        if conference_id:
            try:
                conference = Conference.objects.get(id=conference_id)
                self.stdout.write(self.style.SUCCESS(
                    f'Using existing conference: {conference.name} (ID: {conference.id})'))
            except Conference.DoesNotExist:
                if create_conference:
                    self.stdout.write(self.style.ERROR(
                        f'Conference with ID {conference_id} does not exist, and cannot be created with a specific ID.'))
                    return
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Conference with ID {conference_id} does not exist.')
                    )
                    return
        elif create_conference:
            conference_name = f"Imported Conference {date.today().strftime('%Y-%m-%d')}"
            today = timezone.now().date()
            conference = Conference.objects.create(
                name=conference_name,
                start_date=today,
                end_date=today + timezone.timedelta(days=7)
            )
            self.stdout.write(self.style.SUCCESS(
                f'Created new conference: {conference.name} (ID: {conference.id})'))

        # Get all active tasks for the conference
        tasks = Task.objects.filter(conference=conference, is_active=True)
        task_count = tasks.count()
        self.stdout.write(self.style.SUCCESS(
            f'Found {task_count} active tasks to assign to imported persons'))

        # Get categories if category_ids are provided
        categories = []
        if category_ids:
            categories = list(Category.objects.filter(
                id__in=category_ids, conference=conference))
            self.stdout.write(self.style.SUCCESS(
                f'Found {len(categories)} categories to assign to imported persons'))

            # Notify about categories that were not found
            found_category_ids = [cat.id for cat in categories]
            missing_ids = set(category_ids) - set(found_category_ids)
            if missing_ids:
                self.stdout.write(self.style.WARNING(
                    f'Could not find categories with the following IDs: {", ".join(map(str, missing_ids))}'))

        # Read and process CSV file
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)

                person_count = 0
                person_errors = 0
                task_count = 0
                task_errors = 0
                category_count = 0
                category_errors = 0
                duplicate_codes = 0

                for row in csv_reader:
                    try:
                        stu_number = row.get('stuNumber', '')

                        # Check if a Person with this unique_code already exists
                        unique_code_to_use = None
                        if stu_number:
                            if Person.objects.filter(unique_code=stu_number).exists():
                                self.stdout.write(self.style.WARNING(
                                    f'Person with unique code {stu_number} already exists. Will auto-generate a new code.'))
                                duplicate_codes += 1
                            else:
                                unique_code_to_use = stu_number

                        # Map CSV columns to Person model fields
                        person = Person(
                            conference=conference,
                            first_name=row.get('firstName', ''),
                            last_name=row.get('lastName', ''),
                            telephone=row.get('phone', ''),
                            email=row.get('email', ''),
                            unique_code=unique_code_to_use
                        )
                        person.save()
                        person_count += 1

                        # Assign categories to the person
                        for category in categories:
                            try:
                                person.categories.add(category)
                                category_count += 1
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(
                                    f'Error assigning category {category.name} to person {person.get_full_name()}: {str(e)}'))
                                category_errors += 1

                        # Assign tasks to the person
                        for task in tasks:
                            try:
                                PersonTask.objects.create(
                                    person=person,
                                    task=task,
                                    status=PersonTask.PENDING
                                )
                                task_count += 1
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(
                                    f'Error assigning task {task.name} to person {person.get_full_name()}: {str(e)}'))
                                task_errors += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f'Error importing row: {row}. Error: {str(e)}'))
                        person_errors += 1

                self.stdout.write(self.style.SUCCESS(
                    f'Successfully imported {person_count} persons with {person_errors} errors'
                ))
                if duplicate_codes > 0:
                    self.stdout.write(self.style.WARNING(
                        f'Found {duplicate_codes} duplicate unique codes that were auto-generated'
                    ))
                self.stdout.write(self.style.SUCCESS(
                    f'Successfully assigned {task_count} tasks with {task_errors} errors'
                ))
                self.stdout.write(self.style.SUCCESS(
                    f'Successfully assigned {category_count} categories with {category_errors} errors'
                ))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(
                f'File not found: {csv_file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))
