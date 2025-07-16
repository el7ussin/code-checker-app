# src/blueprints/student_bp.py
import datetime
import uuid
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, current_app, jsonify, get_flashed_messages)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename # For task submissions, recitation uploads
import os # For path operations if needed
import random # For motivational messages if main_bp.dashboard logic moves here fully
import traceback
# Import necessary manager modules and forms
from src import (
    student_manager, auth_manager, curriculum_manager, quran_loader,
    material_manager)
from src.forms import (
    AddGoalForm, EditGoalForm)
from src.decorators import student_required


student_bp = Blueprint('student_bp', __name__) # No common prefix needed here usually

@student_bp.route('/goal/add', methods=['GET', 'POST'])
@login_required
def add_goal(): # Combined GET/POST
    """Displays form and handles adding new goal for logged-in student."""
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can add goals.", "warning"); return redirect(url_for('main_bp.index'))
    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error"); return redirect(url_for('main_bp.dashboard'))

    form = AddGoalForm(request.form) # Pass request.form for POST validation

    if request.method == 'POST' and form.validate_on_submit():
        target_date_obj = form.target_date.data
        target_date_str = target_date_obj.strftime('%Y-%m-%d') if target_date_obj else None
        goal_id = student_manager.admin_bp.add_student_goal(student_id=student_id, goal_type=form.goal_type.data, description=form.description.data, target_date_str=target_date_str)
        if goal_id: flash("New goal added!", "success")
        else: flash("Failed to add new goal.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # Render on GET or failed POST validation
    return render_template('add_goal.html', form=form)



@student_bp.route('/my_goals')
@login_required
def manage_my_goals():
    """Displays page for students to view all their goals."""

    # --- Permission Check: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can manage their goals.", "warning")
        # Redirect non-students student_bpropriately
        if hasattr(current_user, 'role') and current_user.role in ['admin', 'teacher']:
            return redirect(url_for('admin_bp.list_students')) # Or another relevant page
        else:
            return redirect(url_for('main_bp.index'))

    # --- Get Student ID ---
    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("Your user account is not linked to a student record.", "error")
        return redirect(url_for('main_bp.dashboard')) # Stay on main_bp.dashboard

    # --- Fetch ALL Goals ---
    all_goals = []
    try:
        # Call helper to get all goals (not just active)
        all_goals = student_manager.get_student_goals(student_id, status_filter='all')
        # Note: Date formatting should hstudent_bpen within get_student_goals or here if needed
    except Exception as e:
        print(f"Error fetching all goals for student {student_id}: {e}")
        flash("Could not load your goals.", "danger")

    # Render the NEW template, passing the full list of goals
    return render_template('manage_goals.html', # <<< NEW template name
                           all_goals=all_goals)



@student_bp.route('/goal/<int:goal_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_goal(goal_id):
    """Displays form and handles editing an existing goal for the logged-in student."""

    # --- Permission Check 1: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can edit their goals.", "warning")
        return redirect(url_for('main_bp.index')) # Redirect non-students

    # --- Get Student ID ---
    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # --- Fetch Goal & Check Ownership ---
    # Use the helper that checks student_id owns the goal_id
    goal = student_manager.get_goal_by_id(goal_id, student_id)
    if not goal:
        flash("Goal not found or you do not have permission to edit it.", "error")
        return redirect(url_for('manage_my_goals')) # Redirect back to goals list

    # --- Instantiate Form ---
    # Pass request.form on POST for validation, None on GET
    form = EditGoalForm(request.form if request.method == 'POST' else None)

    # --- Handle Form Submission (POST) ---
    if form.validate_on_submit():
        # Get validated data from form
        new_goal_type = form.goal_type.data
        new_description = form.description.data
        new_target_date_obj = form.target_date.data # Date object or None

        # Format date object to string for DB helper function, or None
        new_target_date_str = new_target_date_obj.strftime('%Y-%m-%d') if new_target_date_obj else None

        # Call helper function to update the goal
        if student_manager.update_goal(goal_id, student_id, new_goal_type, new_description, new_target_date_str):
            flash("Goal updated successfully!", "success")
            return redirect(url_for('manage_my_goals')) # Redirect back to the goals list
        else:
            flash("Failed to update goal. Please try again.", "danger")
            # Fall through to re-render form with errors

    # --- Handle Page Load (GET) or Failed POST Validation ---
    # --- Handle GET Request (or failed POST validation) ---
    if request.method == 'GET' and goal:
        # Pre-populate form with existing goal data
        # --- ADD Date Parsing for target_date ---
        target_date_str = goal.get('target_date') # Get date string from DB data
        if target_date_str:
            try:
                # Convert string to date object before passing to form
                goal['target_date'] = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                print(f"Warning: Could not parse target_date string '{target_date_str}' for goal {goal_id}")
                # If parsing fails, don't pass it to the form's DateField via process()
                # It will default to empty. Or set goal['target_date'] = None
                if 'target_date' in goal: del goal['target_date']
        # --- End Date Parsing ---
        form.process(data=goal) # Now pass dict potentially with date object

    # Render template (form has errors if validate_on_submit failed)
    return render_template('edit_goal.html', form=form, goal=goal) # goal dict passed for context display



@student_bp.route('/goal/<int:goal_id>/complete', methods=['POST'])
@login_required
def mark_goal_complete_route(goal_id):
    """Handles marking a student's own goal as complete."""

    # --- Permission Check 1: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can mark their goals complete.", "warning")
        return redirect(url_for('main_bp.index'))

    # --- Get Student ID ---
    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # --- Permission Check 2: Ownership ---
    # Verify the goal exists and belongs to this student before trying to update
    goal = student_manager.get_goal_by_id(goal_id, student_id)
    if not goal:
         flash("Goal not found or you do not have permission to modify it.", "error")
         return redirect(url_for('manage_my_goals'))

    # --- Call Helper Function ---
    if student_manager.mark_goal_complete(goal_id, student_id):
        flash(f"Goal '{goal.get('description','ID: '+str(goal_id))[:30]}...' marked as complete!", 'success')
    else:
        flash("Could not mark goal as complete. Please try again.", 'danger')

    # Redirect back to the goals list page
    return redirect(url_for('manage_my_goals'))



# Quiz Taking (Student)
# In src/blueprints/student_bp.py
@student_bp.route('/my-quizzes')
@login_required
def list_available_quizzes():
    """
    Displays a list of available quizzes for the student,
    filtered by quizzes assigned to their grade.
    """
    if getattr(current_user, 'role', None) != 'student':
        flash("Only students can view available quizzes.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to a student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    available_quizzes = []
    attempted_quiz_data = {}
    
    try:
        # Get the student's grade
        assignment = student_manager.get_student_current_assignment_details(student_id)
        if assignment and assignment.get('grade_id'):
            student_grade_id = assignment['grade_id']
            # Get quizzes for that grade
            available_quizzes = student_manager.get_quizzes_for_grade(student_grade_id)
        else:
            flash("You are not currently assigned to a grade, so no quizzes can be shown.", "info")

        # Get data on quizzes the student has already attempted
        attempted_quiz_data = student_manager.get_attempted_quiz_data(student_id)

    except Exception as e:
        current_app.logger.error(f"Error fetching quizzes for student {student_id}: {e}")
        flash("An error occurred while loading your quizzes.", "danger")

    return render_template('student_quiz_list.html',
                           quizzes=available_quizzes,
                           attempted_quiz_data=attempted_quiz_data)


@student_bp.route('/quiz/<int:quiz_id>/start')
@login_required
def start_quiz(quiz_id):
    """Displays the quiz page for a specific quiz if the student can take it."""
    if getattr(current_user, 'role', None) != 'student':
        flash("Only students can take quizzes.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to a student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # Check if the student has already attempted this quiz
    attempted_quizzes = student_manager.get_attempted_quiz_data(student_id)
    if quiz_id in attempted_quizzes:
        flash("You have already completed this quiz.", "info")
        return redirect(url_for('student_bp.list_available_quizzes'))

    # Fetch the quiz details and its questions
    quiz_info = student_manager.get_quiz_by_id(quiz_id)
    if not quiz_info or not quiz_info.get('is_active'):
        flash("This quiz is not available or does not exist.", "warning")
        return redirect(url_for('student_bp.list_available_quizzes'))

    quiz_questions = student_manager.get_assigned_questions_for_quiz(quiz_id)
    if not quiz_questions:
        flash("This quiz currently has no questions assigned to it.", "info")
        return redirect(url_for('student_bp.list_available_quizzes'))

    # Render the quiz-taking page
    return render_template('quiz.html', quiz=quiz_info, questions=quiz_questions)



@student_bp.route('/quiz/submit', methods=['POST'])
@login_required
def submit_quiz():
    """Processes the submitted quiz answers."""
    if getattr(current_user, 'role', None) != 'student':
        flash("Only students can submit quizzes.", "warning"); return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error"); return redirect(url_for('main_bp.dashboard'))

    score = 0
    total_questions = 0
    attempt_details = []
    question_ids_processed = set()

    # --- ADDED: Get quiz_id from hidden form input ---
    try:
        quiz_id = request.form.get('quiz_id', type=int)
        if not quiz_id:
             # If quiz_id is missing from form, redirect with error
             flash("Quiz ID missing from submission.", "error")
             return redirect(url_for('list_available_quizzes'))
    except (ValueError, TypeError):
         flash("Invalid Quiz ID submitted.", "error")
         return redirect(url_for('list_available_quizzes'))
    # --- END ADDED ---

    try:
        # Loop through submitted answers
        for key, value in request.form.items():
            if key.startswith('answer_'):
                try:
                    question_id = int(key.split('_')[1])
                    selected_option_id = int(value)
                    if question_id in question_ids_processed: continue
                    question_ids_processed.add(question_id)

                    correct_option_id = student_manager.get_correct_option_id(question_id)
                    was_correct = (selected_option_id == correct_option_id)
                    if was_correct: score += 1
                    attempt_details.append({'question_id': question_id, 'selected_option_id': selected_option_id, 'was_correct': was_correct})
                except (IndexError, ValueError, TypeError) as parse_err:
                    print(f"Error parsing submitted answer key/value: {key}={value}, Error: {parse_err}")

        total_questions = len(question_ids_processed)

        if total_questions > 0:
         if hasattr(student_manager, 'save_quiz_attempt'):
              attempt_id = student_manager.save_quiz_attempt(
                  student_id=student_id, score=score, total_questions=total_questions,
                  attempt_details=attempt_details, quiz_id=quiz_id
              )
              if attempt_id:
                   flash("Quiz submitted successfully!", "success")
                   # --- >>> ADD POINTS AWARD <<< ---
                   try:
                       points_to_award = score * 2 # Example: 2 points per correct answer
                       if points_to_award > 0 and hasattr(student_manager, 'award_points'):
                            event_desc = f"Scored {score}/{total_questions} on Quiz ID {quiz_id}"
                            student_manager.award_points(student_id, points_to_award, 'QUIZ_SUBMITTED', event_desc, related_id=attempt_id)
                            flash(f"You earned {points_to_award} points!", "info") # Optional feedback
                   except Exception as e_pts:
                        print(f"Error awarding points for quiz attempt {attempt_id}: {e_pts}")
                   # --- >>> END POINTS AWARD <<< ---
                   return redirect(url_for('student_bp.quiz_results', attempt_id=attempt_id))
              else: flash("Error saving quiz attempt.", "danger")
            
        else: flash("No answers were submitted.", "warning")

    except Exception as e: print(f"Error processing quiz submit: {e}"); traceback.print_exc(); flash("Error submitting quiz.", "danger")
    # Fallback redirect
    return redirect(url_for('student_bp.list_available_quizzes')) # Go back to quiz list on error/no answers



@student_bp.route('/quiz/results/<int:attempt_id>')
@login_required
def quiz_results(attempt_id):
    """Displays the results of a specific quiz attempt for the student."""
    # --- Permission Check: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can view quiz results.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # --- Fetch Results (includes ownership check) ---
    results_data = None
    if hasattr(student_manager, 'get_quiz_attempt_results'):
        results_data = student_manager.get_quiz_attempt_results(attempt_id, student_id)
    else:
        print("Warning: get_quiz_attempt_results helper missing!")
        flash("Could not load quiz results (server error).", "danger")

    if not results_data:
        # Helper returned None (attempt not found or permission denied)
        flash("Quiz attempt not found or you do not have permission to view it.", "error")
        return redirect(url_for('main_bp.dashboard')) # Redirect to main_bp.dashboard

    # Render the NEW results template
    return render_template('quiz_results.html', # <<< NEW template name
                           results=results_data)



#  Materials (Student)

@student_bp.route('/my_materials')
@login_required
def my_materials():
    """Displays the list of materials assigned to the logged-in student's grade."""
    # --- Permission Check: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can view 'My Materials'.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    materials = []
    try:
        materials = student_manager.get_materials_for_student(student_id)
    except Exception as e:
        print(f"Error fetching materials for student {student_id} in route: {e}")
        flash("Could not load your assigned materials.", "danger")

    # Render a NEW template
    return render_template('my_materials.html', materials=materials) # <<< NEW Template Name



@student_bp.route('/materials/<int:material_id>/view')
@login_required
def view_material(material_id):
    """Displays a specific material, embedded if PDF."""
    # --- Permission Check 1: Role ---
    # Allow students, teachers, admins? Or just students? Let's start with students.
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can view materials this way.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # --- Permission Check 2: Can student access this material? ---
    if not student_manager.can_student_access_material(student_id, material_id):
         flash("You do not have permission to access this material.", "error")
         return redirect(url_for('my_materials')) # Go back to their materials list

    # --- Fetch Material Details ---
    material = None
    materials_list = material_manager.get_materials(material_id=material_id) # Reuses existing function
    if materials_list:
        material = materials_list[0]
    else:
        flash("Material not found.", "error")
        return redirect(url_for('my_materials'))

    # --- Check if it's a PDF ---
    is_pdf = material.get('file_type') == 'student_bplication/pdf' or \
             (material.get('filename_orig') and material['filename_orig'].lower().endswith('.pdf'))

    # --- Render Viewer Template ---
    return render_template('view_material.html', # <<< NEW Template Name
                           material=material,
                           is_pdf=is_pdf)



# Tasks (Student)

@student_bp.route('/my_tasks')
@login_required
def my_tasks():
    """Displays the list of tasks assigned to the logged-in student."""
    # --- Permission Check: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can view 'My Tasks'.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    tasks = []
    try:
        tasks = student_manager.get_tasks_for_student(student_id)
    except Exception as e:
        print(f"Error fetching tasks for student {student_id} in route: {e}")
        flash("Could not load your assigned tasks.", "danger")

    # Render a NEW template
    return render_template('my_tasks.html', tasks=tasks) # <<< NEW Template Name



@student_bp.route('/task/<int:task_id>/view')
@login_required
def view_task(task_id):
    """Displays task details for the student (if assigned)."""
     # --- Permission Check: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can view assigned tasks.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    task_data = None
    try:
        task_data = student_manager.get_task_details_for_student_view(student_id, task_id)
    except Exception as e:
        print(f"Error fetching task details for student view (S:{student_id}, T:{task_id}): {e}")
        flash("Error loading task details.", "danger")

    if not task_data:
        # This handles task not found OR student not assigned
        flash("Task not found or you are not assigned to this task.", "warning")
        return redirect(url_for('my_tasks')) # Redirect back to their task list

    # Render a NEW template
    return render_template('view_task.html', task=task_data) # <<< NEW Template Name



@student_bp.route('/task/<int:task_id>/submit', methods=['POST']) # Keep methods=['POST']
@login_required
def submit_task(task_id):
    """Handles the file upload submission for a task."""
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can submit tasks.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # --- Check if already submitted ---
    # It's good practice to prevent resubmission via this route
    existing_submission = student_manager.get_student_submission_status_for_task(student_id, task_id)
    if existing_submission:
        flash("You have already submitted this task.", "warning")
        return redirect(url_for('view_task', task_id=task_id))

    # --- File Handling ---
    uploaded_file = request.files.get('submission_file')
    student_notes = request.form.get('student_notes')
    saved_file_path_rel = None # Relative path to store in DB

    if not uploaded_file or uploaded_file.filename == '':
        flash("No file selected for upload.", "error")
        return redirect(url_for('view_task', task_id=task_id))

    if uploaded_file and allowed_submission_file(uploaded_file.filename):
        try:
            original_filename = uploaded_file.filename
            filename = secure_filename(original_filename)
            # Create a unique filename to prevent overwrites
            unique_prefix = f"{student_id}_{task_id}_{uuid.uuid4().hex[:6]}" # Include student/task ID for context
            secure_name = f"{unique_prefix}_{filename}"

            upload_folder_abs = student_bp.config['TASK_SUBMISSION_UPLOAD_FOLDER']
            # Ensure folder exists (should have been done at startup, but check again)
            os.makedirs(upload_folder_abs, exist_ok=True)

            file_path_abs = os.path.join(upload_folder_abs, secure_name)
            uploaded_file.save(file_path_abs)

            # Store the relative path for web access
            saved_file_path_rel = os.path.join(TASK_SUBMISSION_UPLOAD_FOLDER_REL, secure_name).replace('\\', '/')
            print(f"DEBUG: Saved submission file to: {file_path_abs}")
            print(f"DEBUG: Relative path for DB: {saved_file_path_rel}")

        except Exception as e:
            print(f"ERROR saving uploaded file for task {task_id}, student {student_id}: {e}")
            flash("An error occurred while saving your uploaded file.", "danger")
            return redirect(url_for('view_task', task_id=task_id))
    else:
        flash("Invalid file type selected.", "error")
        return redirect(url_for('view_task', task_id=task_id))

    # --- Save to Database ---
    if saved_file_path_rel: # Only proceed if file was saved successfully
        success = student_manager.add_task_submission(
            student_id=student_id,
            task_id=task_id,
            submission_status='Submitted', # Explicitly set status
            notes=student_notes,
            file_path=saved_file_path_rel # Save the relative path
        )

        if success:
            flash("Task submitted successfully!", "success")
            # Optionally notify teacher here?
            # Consider redirecting to my_tasks instead of the task view after submission
            return redirect(url_for('my_tasks'))
        else:
            # add_task_submission handles IntegrityError (already submitted)
            # This flash might occur if there's another DB error
            flash("Failed to record task submission in database.", "danger")
            # Attempt cleanup? Maybe not needed if DB fails but file saved.
            return redirect(url_for('view_task', task_id=task_id))
    else:
        # This case should ideally not be reached if file saving error handling is correct
        flash("File upload failed, submission not recorded.", "danger")
        return redirect(url_for('view_task', task_id=task_id))



# Games (Student)

@student_bp.route('/games/memory_match')
@login_required
def memory_match_game():
    """Displays the memory match game page for the student."""
    # --- Permission Check: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can play games.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # --- Fetch Game Data ---
    game_data = None
    try:
        # Fetch e.g., 8 pairs (16 cards). Add category filter later if needed.
        if hasattr(student_manager, 'get_memory_pairs_for_game'):
            game_data = student_manager.get_memory_pairs_for_game(num_pairs=8)
        else: print("Warning: get_memory_pairs_for_game helper missing!")

        if not game_data:
             flash("Could not load data for the memory game. Maybe no pairs have been added?", "warning")
             return redirect(url_for('main_bp.dashboard')) # Go back if no data

    except Exception as e:
        print(f"Error loading memory match game data: {e}")
        flash("An error occurred loading the game.", "danger")
        return redirect(url_for('main_bp.dashboard'))

    # Render the NEW template, passing the game data dictionary
    # game_data contains {'pairs': [...], 'shuffled_items': [...]}
    return render_template('memory_match_game.html', # <<< NEW template name
                           game_data=game_data)



# Curriculum & Lessons (Student) 

@student_bp.route('/my_curriculum')
@login_required
def my_curriculum():
    """Displays the structured curriculum for the logged-in student."""

    # --- Permission Check: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can view the curriculum page.", "warning")
        # Redirect non-students student_bpropriately
        if hasattr(current_user, 'role') and current_user.role in ['admin', 'teacher']:
            return redirect(url_for('main_bp.dashboard')) # Teachers go to their main_bp.dashboard
        else:
            return redirect(url_for('main_bp.index')) # Others to main_bp.index

    # --- Get Student ID ---
    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("Your user account is not linked to a student record.", "error")
        return redirect(url_for('main_bp.dashboard')) # Stay on main_bp.dashboard

    # --- Fetch Curriculum Data ---
    curriculum_data = {} # Default empty
    student_assignment = None # To display grade context
    try:
        # Fetch the structured curriculum (Term -> Category -> Lesson List)
        if hasattr(curriculum_manager, 'get_curriculum_for_student'):
            curriculum_data = curriculum_manager.get_curriculum_for_student(student_id)
        else:
            print("ERROR: curriculum_manager.get_curriculum_for_student helper missing!")
            flash("Could not load curriculum data (server error).", "error")

        # Get student's assignment for context display in template (optional)
        if hasattr(student_manager, 'get_student_current_assignment_details'):
            student_assignment = student_manager.get_student_current_assignment_details(student_id)

    except Exception as e:
        print(f"Error fetching curriculum data for student {student_id} in route: {e}")
        traceback.print_exc()
        flash("An error occurred loading the curriculum.", "danger")

    # Render the NEW template
    # Ensure you create 'templates/my_curriculum.html' next
    return render_template('my_curriculum.html',
                           curriculum_data=curriculum_data,
                           student_assignment=student_assignment) # Pass assignment for context



@student_bp.route('/lesson/<int:lesson_id>')
@login_required
def view_lesson(lesson_id):
    """Displays the detail page for a specific lesson."""

    # --- Permission Check 1: Role (Only students view lessons this way?) ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        # Redirect teachers/admins elsewhere? Maybe to an edit page later?
        return redirect(url_for('teacher_my_lessons'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # --- Permission Check 2: Can student access this lesson's grade? ---
    # Ensure curriculum_manager is imported and has the function
    if not hasattr(curriculum_manager, 'can_student_access_lesson') or \
       not curriculum_manager.can_student_access_lesson(student_id, lesson_id):
         flash("You do not have permission to access this lesson.", "error")
         return redirect(url_for('main_bp.dashboard')) # Redirect back to main_bp.dashboard

    # --- Fetch Lesson Data ---
    lesson_data = None
    try:
        # Ensure curriculum_manager is imported and has the function
        if hasattr(curriculum_manager, 'get_lesson_details'):
            lesson_data = curriculum_manager.get_lesson_details(lesson_id)
        else:
             print("ERROR: curriculum_manager.get_lesson_details function missing!")
             flash("Server error: Could not load lesson details.", "error")

    except Exception as e:
        print(f"Error fetching lesson details for L:{lesson_id} in route: {e}")
        flash("Error loading lesson details.", "danger")

    if not lesson_data:
        # This handles lesson not found after permission check passed
        flash("Lesson not found.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # --- Render Template ---
    # Ensure the template name matches the file you create
    print(f"DEBUG [view_lesson]: Final lesson_data['materials'] before render: {lesson_data.get('materials')}") # Add this
    return render_template('lesson_detail.html',
                           lesson=lesson_data)



# Attendance (Student)

@student_bp.route('/my_attendance')
@login_required
def my_attendance():
    """Displays the logged-in student's attendance summary and log."""
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can view this page.", "warning")
        return redirect(url_for('main_bp.index'))

    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard'))

    # Fetch data using the new manager functions
    # Consider adding date range filters here later if needed
    attendance_summary = {}
    attendance_log = []
    try:
        # Ensure the manager functions exist
        if hasattr(student_manager, 'get_attendance_summary_for_student'):
            attendance_summary = student_manager.get_attendance_summary_for_student(student_id)
        else:
            print("ERROR: get_attendance_summary_for_student function missing!")
            flash("Could not load attendance summary.", "error")

        if hasattr(student_manager, 'get_attendance_for_student'):
             # Maybe limit the log initially, e.g., last 30 days?
             # For now, get all logs.
            attendance_log = student_manager.get_attendance_for_student(student_id)
        else:
            print("ERROR: get_attendance_for_student function missing!")
            flash("Could not load attendance log.", "error")

    except Exception as e:
        print(f"Error loading attendance data for student {student_id}: {e}")
        flash("An error occurred loading attendance data.", "danger")

    # Render the NEW template
    return render_template('my_attendance.html',
                           summary=attendance_summary,
                           log=attendance_log)



# Leaderboard (Students)

@student_bp.route('/leaderboard')
@login_required # Ensure user is logged in
def leaderboard():
    """Displays the points leaderboard."""

    # Decide who can view: Just students? Or teachers/admins too?
    # Let's start with students only for now.
    if not hasattr(current_user, 'role') or current_user.role != 'student':
         flash("Leaderboard is currently only available for students.", "info")
         # Redirect non-students student_bpropriately
         if hasattr(current_user, 'role') and current_user.role in ['admin', 'teacher']:
             return redirect(url_for('main_bp.dashboard')) # Redirect teacher/admin to their main_bp.dashboard
         else:
             return redirect(url_for('main_bp.index')) # Others to main_bp.index

    leaderboard_data = []
    try:
        # Fetch the top N students using the new manager function
        # Ensure get_students_for_leaderboard exists in student_manager
        if hasattr(student_manager, 'get_students_for_leaderboard'):
            leaderboard_data = student_manager.get_students_for_leaderboard(limit=25) # Get Top 25
        else:
            print("ERROR: student_manager.get_students_for_leaderboard function missing!")
            flash("Could not load leaderboard data (server error).", "error")

    except Exception as e:
        print(f"Error fetching leaderboard data in route: {e}")
        flash("An error occurred loading the leaderboard.", "danger")

    # Render the new leaderboard template, passing the ranked student data
    # We also pass current_user.id to highlight the logged-in student
    return render_template('leaderboard.html', # <<< NEW template name
                           leaderboard=leaderboard_data,
                           current_user_id=current_user.id) # Pass current user's ID



# Recitation (Students)

@student_bp.route('/my-recitation-history')
@login_required
def my_recitation_history():
    """Displays the student's full recitation history."""

    # 1. --- Permission Check: Role ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        flash("Only students can view their recitation history.", "warning")
        return redirect(url_for('main_bp.index')) # Redirect non-students

    # 2. --- Get Student ID ---
    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
        flash("User account not linked to student record.", "error")
        return redirect(url_for('main_bp.dashboard')) # Stay on main_bp.dashboard

    # 3. --- Fetch ALL Recitation History ---
    history_list = []
    try:
        # Ensure the manager function fetches 'recording_path'
        history_list = student_manager.get_student_recitation_history(student_id)
        # Optional: Format dates here if not done in manager
        for item in history_list:
             recite_date_str = item.get('recitation_date')
             try: item['recitation_date_formatted'] = datetime.datetime.fromisoformat(recite_date_str).strftime('%Y-%m-%d %H:%M') if recite_date_str else "N/A"
             except: item['recitation_date_formatted'] = recite_date_str # Fallback
    except Exception as e:
        print(f"Error fetching recitation history for student {student_id} in route: {e}")
        flash("Could not load your recitation history.", "danger")

    # 4. --- Render the NEW template ---
    return render_template('my_recitation_history.html', # <<< Use the new template name
                           history_list=history_list,
                           title="My Recitation History")



@student_bp.route('/recitation/upload', methods=['POST'])
@login_required
def handle_recitation_upload():
    # 1. --- Permission & Student ID Check ---
    if not hasattr(current_user, 'role') or current_user.role != 'student':
        return jsonify({"success": False, "message": "Only students can upload recordings."}), 403
    student_id = student_manager.get_student_id_for_user(current_user.id)
    if not student_id:
         return jsonify({"success": False, "message": "Student profile not found."}), 400

    # 2. --- Get Data from Request ---
    audio_file = request.files.get('audio_file')
    recording_type = request.form.get('recording_type') # Should be 'general_review' now
    # Still try to get specific numbers in case JS sends them or for future use
    surah_num_str = request.form.get('surah_num')
    start_ayah_str = request.form.get('start_ayah')
    end_ayah_str = request.form.get('end_ayah')

    # 3. --- Basic Validation ---
    if not audio_file or audio_file.filename == '':
        return jsonify({"success": False, "message": "No audio file submitted."}), 400
    # Add other file validation if needed

    # 4. --- Save the File ---
    saved_file_path_rel = None
    file_path_abs = None # Define file_path_abs here
    try:
        # Define target folder
        upload_folder_abs = os.path.join(current_student_bp.static_folder, 'uploads', 'recordings')
        os.makedirs(upload_folder_abs, exist_ok=True)

        # Generate secure & unique filename
        original_filename = secure_filename(audio_file.filename or 'recording.wav')
        unique_prefix = str(uuid.uuid4().hex[:8])

        # --- Modify filename based on type ---
        if recording_type == 'general_review':
             filename_part = f"s{student_id}_general_{unique_prefix}_{original_filename}"
        else:
            # Try to parse specific surah/ayah for filename, fallback to 0
            try: s = int(surah_num_str) if surah_num_str else 0
            except: s = 0
            try: a_start = int(start_ayah_str) if start_ayah_str else 0
            except: a_start = 0
            filename_part = f"s{student_id}_r{s}a{a_start}_{unique_prefix}_{original_filename}"
        # --- End modification ---

        secure_name = filename_part
        file_path_abs = os.path.join(upload_folder_abs, secure_name) # Assign to outer scope variable

        # Generate relative path for DB
        saved_file_path_rel = os.path.join('uploads', 'recordings', secure_name).replace('\\', '/')

        # Save the actual file
        audio_file.save(file_path_abs)
        print(f"DEBUG: Saved recording file to: {file_path_abs}")

    except Exception as e:
        print(f"ERROR saving recording file for student {student_id}: {e}")
        return jsonify({"success": False, "message": "Server error saving file."}), 500

    # 5. --- Add Database Log Entry ---
    log_id = None
    if saved_file_path_rel: # Only proceed if file was saved
        try:
            # --- >>> MODIFIED LOGIC for Surah/Ayah <<< ---
            if recording_type == 'general_review':
                log_surah, log_start, log_end = 0, 0, 0 # Use placeholders for general review
                default_notes = "General review recording of memorized Surahs."
            else:
                # Attempt to parse specific numbers if provided (fallback to 0)
                try: log_surah = int(surah_num_str) if surah_num_str else 0
                except: log_surah = 0
                try: log_start = int(start_ayah_str) if start_ayah_str else 0
                except: log_start = 0
                try: log_end = int(end_ayah_str) if end_ayah_str else log_start
                except: log_end = log_start
                default_notes = f"Student submission awaiting review (Section: {log_surah}:{log_start}-{log_end})."
            # --- >>> END MODIFIED LOGIC <<< ---

            # Call the manager function with determined values
            log_id = student_manager.add_recitation_log(
                student_id=student_id,
                surah_num=log_surah,
                start_ayah=log_start,
                end_ayah=log_end,
                feedback_notes=default_notes, # Use the student_bpropriate default notes
                quality_rating=None,
                recording_path=saved_file_path_rel # Pass the relative path
            )

            if not log_id:
                print(f"CRITICAL ERROR: File saved ({saved_file_path_rel}) but failed to create recitation_log entry.")
                # Clean up the orphaned file if DB insert fails
                try:
                    if file_path_abs and os.path.exists(file_path_abs):
                         os.remove(file_path_abs)
                         print(f"DEBUG: Cleaned up orphaned file: {file_path_abs}")
                except OSError as e_remove:
                     print(f"ERROR: Failed to clean up orphaned file {file_path_abs}: {e_remove}")
                return jsonify({"success": False, "message": "Failed to save submission log."}), 500

        except Exception as db_err:
             print(f"ERROR creating recitation_log entry for student {student_id}: {db_err}")
             # Clean up the orphaned file if DB insert fails
             try:
                 if file_path_abs and os.path.exists(file_path_abs):
                     os.remove(file_path_abs)
                     print(f"DEBUG: Cleaned up orphaned file: {file_path_abs}")
             except OSError as e_remove:
                 print(f"ERROR: Failed to clean up orphaned file {file_path_abs}: {e_remove}")
             return jsonify({"success": False, "message": "Server error logging submission."}), 500

    # 6. --- Return Success Response ---
    print(f"DEBUG: Successfully processed recording upload. Log ID: {log_id}")
    # TODO: Notify teacher maybe?

    return jsonify({"success": True, "message": "Recording submitted successfully!", "log_id": log_id}), 201 # 201 Created



@student_bp.route('/select-subject')
@login_required
@student_required
def select_subject():
    """
    Displays the main subject selection dashboard for a student.
    """
    subjects = [
        {
            "name": "Islamic Studies",
            # This links to your existing detailed dashboard
            "url": "main_bp.dashboard",
            "icon": "fas fa-moon",
            "description": "Track your Qur'an journey, recitation, and goals."
        },
        {
            "name": "Arabic",
            "url": "student_bp.subject_arabic",
            "icon": "fas fa-language",
            "description": "Engage with lessons and activities for Arabic language."
        },
        {
            "name": "Social & Moral Education",
            "url": "student_bp.subject_social",
            "icon": "fas fa-users",
            "description": "Explore topics in social and moral studies."
        }
    ]
    return render_template('select_subject.html', subjects=subjects)

# In src/blueprints/student_bp.py, replace the old subject_arabic function with this one.
# Make sure to import the student_manager at the top of the file:
# from src import student_manager

@student_bp.route('/subject/arabic')
@login_required
@student_required
def subject_arabic():
    """
    Displays the dashboard for the Arabic subject.
    """
    # --- CHANGE THIS SECTION ---
    # First, get the student object from the user, then get the ID from that.
    # Add a check to make sure the student record exists.
    if not current_user.student:
        flash("Could not find an associated student profile.", "error")
        return redirect(url_for('student_bp.select_subject'))

    student_id = current_user.student.student_id
    # --- END OF CHANGE ---

    # Get the data from our new manager function
    dashboard_data = student_manager.get_arabic_dashboard_data(student_id)
    
    # Render a new template, passing the data to it
    return render_template('arabic_dashboard.html', **dashboard_data)



# In src/blueprints/student_bp.py, replace the old subject_social function.

@student_bp.route('/subject/social')
@login_required
@student_required
def subject_social():
    """
    Displays the dashboard for the Social & Moral Education subject.
    """
    if not current_user.student:
        flash("Could not find an associated student profile.", "error")
        return redirect(url_for('student_bp.select_subject'))

    student_id = current_user.student.student_id
    
    # Get data from our new manager function
    dashboard_data = student_manager.get_social_dashboard_data(student_id)
    
    # Render the new dashboard template
    return render_template('social_dashboard.html', **dashboard_data)