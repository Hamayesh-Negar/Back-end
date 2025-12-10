/**
 * Category Admin JavaScript
 * Handles dynamic filtering of tasks based on selected conference
 */

(function ($) {
    'use strict';

    $(document).ready(function () {
        // Get the conference and tasks fields
        var $conferenceField = $('#id_conference');
        var $tasksField = $('#id_tasks');

        if ($conferenceField.length && $tasksField.length) {
            // Store original tasks data
            var allTasks = [];

            // Collect all task options with their conference info
            $('#id_tasks option').each(function () {
                var $option = $(this);
                allTasks.push({
                    value: $option.val(),
                    text: $option.text(),
                    element: $option.clone()
                });
            });

            // Function to filter tasks by conference
            function filterTasksByConference() {
                var selectedConference = $conferenceField.val();

                if (!selectedConference) {
                    // If no conference selected, show all tasks
                    return;
                }

                // Get the tasks for this conference via AJAX
                $.ajax({
                    url: '/admin/person/task/',
                    data: {
                        conference__id__exact: selectedConference,
                        is_active__exact: 1,
                        t: new Date().getTime() // Cache buster
                    },
                    success: function (data) {
                        // Parse the response to get task IDs
                        var $tempDiv = $('<div>').html(data);
                        var availableTaskIds = [];

                        $tempDiv.find('tr.row1, tr.row2').each(function () {
                            var $row = $(this);
                            var taskId = $row.find('input[name="_selected_action"]').val();
                            if (taskId) {
                                availableTaskIds.push(taskId);
                            }
                        });

                        // Filter the task options
                        var $tasksFrom = $('#id_tasks_from');
                        var $tasksTo = $('#id_tasks_to');

                        if ($tasksFrom.length && $tasksTo.length) {
                            // Using filter_horizontal widget
                            $tasksFrom.find('option').each(function () {
                                var $option = $(this);
                                if (availableTaskIds.indexOf($option.val()) === -1) {
                                    $option.hide();
                                } else {
                                    $option.show();
                                }
                            });
                        } else {
                            // Using regular select or checkbox widget
                            $tasksField.find('option').each(function () {
                                var $option = $(this);
                                if ($option.val() && availableTaskIds.indexOf($option.val()) === -1) {
                                    $option.hide();
                                } else {
                                    $option.show();
                                }
                            });
                        }
                    }
                });
            }

            // Bind change event to conference field
            $conferenceField.on('change', filterTasksByConference);

            // Run on page load if conference is already selected
            if ($conferenceField.val()) {
                filterTasksByConference();
            }
        }

        // Add visual indicators for category tasks
        $('.field-tasks .help').after(
            '<p class="help" style="color: #666; font-style: italic; margin-top: 5px;">' +
            '<strong>Note:</strong> When you add or remove tasks from this category, ' +
            'they will be automatically assigned to or removed from all current members.' +
            '</p>'
        );
    });

})(django.jQuery);
