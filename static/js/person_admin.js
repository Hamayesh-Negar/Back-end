(function ($) {
  $(document).ready(function () {
    // Cache DOM elements
    const conferenceSelect = $("#id_conference");
    const tasksFieldset = $("fieldset.tasks-fieldset");

    // If there's no tasks fieldset yet, wrap the tasks field in a fieldset for better styling
    if (!tasksFieldset.length) {
      const tasksField = $(".field-tasks");
      if (tasksField.length) {
        tasksField.wrap(
          '<fieldset class="tasks-fieldset module aligned"></fieldset>'
        );
        tasksField.closest("fieldset").prepend("<h2>Assign Tasks</h2>");
      }
    }

    // Function to filter tasks based on selected conference
    function filterTasksByConference() {
      const conferenceId = conferenceSelect.val();
      if (!conferenceId) {
        // If no conference selected, hide the tasks field
        $(".field-tasks").hide();
        return;
      }

      // Show the tasks field
      $(".field-tasks").show();

      // Get all task checkboxes
      const taskCheckboxes = $("#id_tasks input[type='checkbox']");

      // Show loading indicator
      $(".field-tasks ul").before(
        '<div class="loading">Filtering tasks...</div>'
      );

      // Make the task checkboxes dynamically get their conference attribute
      // This only needs to be done once, but we'll do it each time to ensure it works
      taskCheckboxes.each(function () {
        const checkboxId = $(this).attr("id");
        const taskId = $(this).val();

        // If we haven't yet added a data attribute for the conference, add it
        if (!$(this).data("conference")) {
          // Add a data attribute to keep track of which conference this task belongs to
          // We'll use Django's related-lookup URL to get this information
          $.get("/admin/person/task/" + taskId + "/change/", function (data) {
            // Extract the conference ID from the page
            const conferenceMatch = data.match(
              /id="id_conference"\s+value="(\d+)"/
            );
            if (conferenceMatch && conferenceMatch[1]) {
              $("#" + checkboxId).data("conference", conferenceMatch[1]);
              // After setting the data, refilter
              filterTasksUI();
            }
          });
        }
      });

      // Do the actual filtering in the UI
      filterTasksUI();
    }

    // Filter the tasks in the UI based on the conference
    function filterTasksUI() {
      const conferenceId = conferenceSelect.val();
      const taskCheckboxes = $("#id_tasks input[type='checkbox']");

      // Remove loading indicators
      $(".field-tasks .loading").remove();

      // Show/hide tasks based on their conference
      taskCheckboxes.each(function () {
        const taskConference = $(this).data("conference");
        const checkboxRow = $(this).closest(".checkbox-row");
        if (!checkboxRow.length) {
          // If there's no checkbox-row, wrap it
          $(this)
            .next("label")
            .addBack()
            .wrapAll("<div class='checkbox-row'></div>");
        }

        // Show or hide based on conference match
        if (taskConference && taskConference == conferenceId) {
          $(this).closest(".checkbox-row").show();
        } else if (taskConference && taskConference != conferenceId) {
          // Uncheck if not in current conference and hide
          $(this).prop("checked", false);
          $(this).closest(".checkbox-row").hide();
        } else {
          // No conference data yet, keep it visible for now
          $(this).closest(".checkbox-row").show();
        }
      });

      // If no visible tasks, show a message
      if ($("#id_tasks .checkbox-row:visible").length === 0) {
        $("#id_tasks").append(
          "<p class='no-tasks'>No tasks available for this conference. Create tasks first.</p>"
        );
      } else {
        $("#id_tasks .no-tasks").remove();
      }
    }

    // Update tasks on conference change
    conferenceSelect.on("change", filterTasksByConference);

    // Initial filtering if conference is already selected
    if (conferenceSelect.val()) {
      filterTasksByConference();
    } else {
      // Hide tasks field initially if no conference selected
      $(".field-tasks").hide();
    }
  });
})(django.jQuery);
