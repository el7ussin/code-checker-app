# src/blueprints/admin_bp.py
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, current_app, get_flashed_messages, send_from_directory)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import datetime
import string
from collections import Counter, defaultdict
import traceback
from src import (
    auth_manager, student_manager, reporting, material_manager,
    curriculum_manager, database, quran_loader)
from src.forms import (
    LoginForm, AddUserForm, AddStudentUserForm, EditStudentForm,
    EditHifzForm, EditRecitationForm, AddGoalForm,
    EditGradeForm, EditCategoryForm, InputRequired, EditSubjectForm,
    EditStudentAssignmentForm, EditGoalForm, AddQuizQuestionForm, EditQuizQuestionForm,
    QuizForm, EditUserForm, MaterialUploadForm, CreateTaskForm, AttachMaterialForm, AddMemoryPairForm,
    AssignTaskForm, GradeSubmissionForm, AnnouncementForm, MatchingPairForm,
    AssignTeachersToStudentForm, AddClassForm, AddLessonForm, AddHadithLinkForm, EditLessonForm,
    EditSubjectForm, EditCategoryForm, EditGradeForm, AddSectionForm, BulkUserUploadForm, RubricForm)
from src.decorators import admin_required
import pandas as pd


admin_bp = Blueprint(
    'admin_bp',
    __name__,
    # --- THIS IS THE FIX ---
    url_prefix='/admin'
)

# --- Admin Dashboard ---
@admin_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Initialize all our variables
    user_counts = {'admin': 0, 'teacher': 0, 'student': 0, 'total': 0}
    grade_count_val = "N/A"
    student_profile_count = "N/A"
    subject_count = "N/A"    # <-- NEW
    category_count = "N/A"   # <-- NEW
    section_count = "N/A"    # <-- NEW

    try:
        # User counts (existing)
        if hasattr(auth_manager, 'get_user_counts_by_role'):
            user_counts = auth_manager.get_user_counts_by_role()
        
        # Grade and Student counts (existing)
        if hasattr(student_manager, 'get_total_grade_count'):
            grade_count_val = student_manager.get_total_grade_count()
        else:
            current_app.logger.warning("student_manager.get_total_grade_count function not found.")
            grade_count_val = "Err"
            
        if hasattr(student_manager, 'get_student_profile_count'):
            student_profile_count = student_manager.get_student_profile_count()
        else:
            current_app.logger.warning("get_student_profile_count not found.")

        # --- NEW SECTION TO ADD ---
        # Get total subjects, categories, and sections
        if hasattr(student_manager, 'get_total_subject_count'):
             subject_count = student_manager.get_total_subject_count()
        if hasattr(student_manager, 'get_total_category_count'):
             category_count = student_manager.get_total_category_count()
        if hasattr(student_manager, 'get_total_section_count'):
             section_count = student_manager.get_total_section_count()
        # --- END OF NEW SECTION ---
   
    except Exception as e:
        current_app.logger.error(f"Error loading data for admin dashboard: {e}")
        flash("Could not load all dashboard statistics.", "warning")
        user_counts = {'admin': 'N/A', 'teacher': 'N/A', 'student': 'N/A', 'total': 'N/A'}
        grade_count_val = "N/A"
        student_profile_count = "N/A"
        subject_count = "N/A"
        category_count = "N/A"
        section_count = "N/A"


# --- ADD THIS SECTION ---
    teacher_performance_data = []
    try:
        # Call the new function to get teacher performance metrics
        if hasattr(auth_manager, 'get_teacher_performance_summary'):
            teacher_performance_data = auth_manager.get_teacher_performance_summary()
        else:
            current_app.logger.warning("auth_manager.get_teacher_performance_summary function not found.")
    except Exception as e:
        current_app.logger.error(f"Error loading teacher performance data for admin dashboard: {e}")
        flash("Could not load teacher performance statistics.", "warning")
    # --- END OF ADDED SECTION ---
        

# --- ADD THIS SECTION ---
    section_progress_data = []
    try:
        # Call the new function to get section progress metrics
        if hasattr(reporting, 'get_section_progress_summary'):
            section_progress_data = reporting.get_section_progress_summary()
        else:
            current_app.logger.warning("reporting.get_section_progress_summary function not found.")
    except Exception as e:
        current_app.logger.error(f"Error loading section progress data for admin dashboard: {e}")
        flash("Could not load section progress statistics.", "warning")
    # --- END OF ADDED SECTION ---

    admin_announcements_list = []
    try:
        if hasattr(auth_manager, 'get_announcements_for_user'):
            admin_announcements_list = auth_manager.get_announcements_for_user(
                user_id=current_user.id, role='admin'
            )
        else:
            current_app.logger.error("ERROR: auth_manager.get_announcements_for_user function missing!")
    except Exception as e:
        current_app.logger.error(f"Error fetching announcements for admin dashboard: {e}")

    return render_template('admin_dashboard.html', 
                           user_counts=user_counts,
                           grade_count=grade_count_val,
                           student_profile_count=student_profile_count,
                           subject_count=subject_count,      # <-- NEW
                           category_count=category_count,    # <-- NEW
                           section_count=section_count,      # <-- NEW
                           announcements=admin_announcements_list,
                           teacher_performance=teacher_performance_data,
                           section_progress=section_progress_data)

# --- User Management ---
# In src/blueprints/admin_bp.py, replace the entire list_admin_users function

@admin_bp.route('/users')
@login_required
@admin_required
def list_admin_users():
    admins = []
    teachers = []
    # FIX: Use a standard dictionary to build the structure explicitly
    students_structured = {}
    unassigned_students = []

    try:
        all_users = auth_manager.get_all_users()
        all_student_profiles_list = student_manager.get_all_students_with_assignments()
        all_student_profiles = {p['user_id']: p for p in all_student_profiles_list}

        for user in all_users:
            if user['role'] == 'admin':
                admins.append(user)
            
            elif user['role'] == 'teacher':
                user['assignment_summary'] = auth_manager.get_assigned_grade_section_summary_for_teacher(user['user_id'])
                teachers.append(user)

            elif user['role'] == 'student':
                student_details = all_student_profiles.get(user['user_id'])

                if student_details:
                    # Determine keys, providing a default for any None values
                    subj = student_details.get('subject_name') or 'Unassigned'
                    cat = student_details.get('category_name') or 'Unassigned'
                    grade = student_details.get('grade_name') or 'Unassigned'
                    sec = student_details.get('section_letter') or 'Unassigned'
                    
                    if 'Unassigned' in [subj, cat, grade, sec]:
                        unassigned_students.append(student_details)
                    else:
                        # --- FIX: Build the nested dictionary manually with setdefault ---
                        # This is more explicit and guarantees the correct structure.
                        subject_level = students_structured.setdefault(subj, {})
                        category_level = subject_level.setdefault(cat, {})
                        grade_level = category_level.setdefault(grade, {})
                        section_level = grade_level.setdefault(sec, [])
                        section_level.append(student_details)
                else:
                    # This is an orphan user with no profile
                    unassigned_students.append(user)

    except Exception as e:
        current_app.logger.error(f"Error fetching and processing users for admin list: {e}")
        traceback.print_exc()
        flash("An error occurred while loading the user list.", "danger")

    return render_template('admin_users.html',
                           admins=admins,
                           teachers=teachers,
                           students_structured=students_structured,
                           unassigned_students=unassigned_students)



@admin_bp.route('/add_teacher', methods=['GET', 'POST'])
@login_required
@admin_required
def add_teacher():
    form = AddUserForm(request.form)
    if request.method == 'POST' and form.validate_on_submit(): # validate_on_submit checks method
        success_user_id = auth_manager.create_user(
            username=form.username.data, password=form.password.data, role='teacher',
            full_name=form.full_name.data, email=form.email.data
        )
        if success_user_id:
            teacher_username = form.username.data
            flash(f'Teacher account "{teacher_username}" created successfully. Now assign grades/sections.', 'success')
            return redirect(url_for('admin_bp.admin_manage_teacher_assignments', teacher_user_id=success_user_id))
        else: # create_user should flash its own error if username/email exists
            if not get_flashed_messages(): # Avoid duplicate messages
                flash(f'Failed to create teacher "{form.username.data}". Username/Email may exist or other error.', 'error')
    return render_template('add_teacher.html', form=form)


@admin_bp.route('/add_student_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_student_user():
    form = AddStudentUserForm()
    try:
        all_subjects = student_manager.get_all_subjects()
        form.subject_id.choices = [(s['subject_id'], s['subject_name']) for s in all_subjects]
        form.subject_id.choices.insert(0, ('', '-- Select Subject --'))
    except Exception as e:
        current_app.logger.error(f"Error populating subject choices: {e}")
        flash("Could not load subject list.", "error")
        form.subject_id.choices = [('', '-- Error --')]

    form.grade_id.choices = [('', '-- Select Subject First --')] # Will be populated by JS or on POST

    if request.method == 'POST':
        submitted_subject_id_str = request.form.get('subject_id')
        if submitted_subject_id_str:
            try:
                submitted_subject_id = int(submitted_subject_id_str)
                grades_for_subject = student_manager.get_grades_for_subject(submitted_subject_id)
                form.grade_id.choices = [(g['grade_id'], f"{g.get('category_name','')} / {g['grade_name']}") for g in grades_for_subject]
                form.grade_id.choices.insert(0, ('', '-- Select Grade --'))
            except (ValueError, TypeError, Exception) as e:
                current_app.logger.error(f"Error populating grade choices during POST for add_student_user: {e}")
                form.grade_id.choices = [('', '-- Error Loading Grades --')]

    if form.validate_on_submit():
        try:
            username = form.username.data
            password = form.password.data
            name = form.name.data
            contact = form.contact_info.data
            subject_id = form.subject_id.data
            grade_id = form.grade_id.data
            section_letter = form.section_letter.data

            new_user_id = auth_manager.create_user(username, form.password.data, role='student', full_name=form.name.data)
           
            if not new_user_id:
                # The auth_manager prints the specific error, let's flash a user-friendly one.
                flash(f"Could not create user '{username}'. The username may already be taken.", "error")
                # Stay on the same page to allow the user to correct the form
                return render_template('add_student_user.html', form=form)

            student_profile_id = student_manager.add_student(name=form.name.data, contact_info=form.contact_info.data or None, user_id=new_user_id)
            if not student_profile_id:
                flash(f'User "{username}" created, but FAILED to create linked student profile.', 'danger')
                # Optional: Clean up the created user if the profile fails
                auth_manager.delete_user(new_user_id)
                return render_template('add_student_user.html', form=form)

            # --- Assignment logic remains the same ---
            assign_success = student_manager.assign_student_to_grade_section(student_profile_id, form.grade_id.data, form.section_letter.data)
            if not assign_success:
                flash(f'User & profile created, BUT failed to assign to section. Assign manually.', 'warning')
            else:
                flash(f'Student user "{username}" and profile created and assigned successfully!', 'success')
            
            return redirect(url_for('admin_bp.list_admin_users'))

        except Exception as e:
            # This will now catch other, unexpected errors
            current_app.logger.error(f"An unexpected error occurred during student creation: {e}")
            flash('An unexpected server error occurred.', 'danger')

    elif request.method == 'POST':
        flash("Please correct the errors shown in the form.", "warning")

    return render_template('add_student_user.html', form=form)


@admin_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = auth_manager.get_user_details(user_id)
    if not user:
        flash(f"User with ID {user_id} not found.", "error")
        return redirect(url_for('admin_bp.list_admin_users'))

    form = EditUserForm(request.form if request.method == 'POST' else None)

    if form.validate_on_submit():
        if user_id == current_user.id and form.role.data != 'admin':
            flash("Admins cannot remove their own admin role.", "warning")
        else:
            new_password = form.new_password.data if form.new_password.data else None
            if hasattr(auth_manager, 'update_user'):
                success = auth_manager.update_user(
                    user_id=user_id, username=form.username.data, full_name=form.full_name.data,
                    email=form.email.data, new_password=new_password, role=form.role.data
                )
                if success:
                    flash(f"User '{form.username.data}' updated successfully!", "success")
                    return redirect(url_for('admin_bp.list_admin_users'))
                else: # auth_manager.update_user should flash specific errors
                    if not get_flashed_messages(with_categories=True):
                        flash("Failed to update user. Check logs or ensure data is unique.", "danger")
            else:
                flash("Backend function 'update_user' is missing!", "error")
    elif request.method == 'GET':
        form_data = user.copy()
        form_data.pop('password_hash', None)
        form_data.pop('new_password', None)
        form_data.pop('confirm_password', None)
        form.process(data=form_data)
    elif request.method == 'POST': # Validation failed
        flash("Please correct the errors below.", "warning")

    return render_template('admin_edit_user.html', form=form, user=user)

@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    if user_id == current_user.id:
        flash("You cannot delete your own administrator account.", "danger")
        return redirect(url_for('admin_bp.list_admin_users'))
    user_to_delete = auth_manager.get_user_details(user_id)
    username_to_delete = user_to_delete['username'] if user_to_delete else f"ID {user_id}"
    if hasattr(auth_manager, 'delete_user'):
        if auth_manager.delete_user(user_id):
            flash(f"User '{username_to_delete}' and all associated data deleted successfully!", 'success')
        else:
            flash(f"Failed to delete user '{username_to_delete}'. User might not exist or a database error occurred.", 'danger')
    else:
        flash("Backend function 'delete_user' is missing!", "error")
        current_app.logger.error("ERROR: auth_manager.delete_user function not found!")
    return redirect(url_for('admin_bp.list_admin_users'))

@admin_bp.route('/teacher/<int:teacher_user_id>/manage_assignments', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_manage_teacher_assignments(teacher_user_id):
    teacher = auth_manager.get_user_details(teacher_user_id)
    if not teacher or teacher.get('role') != 'teacher':
        flash("Teacher not found or user is not a teacher.", "error")
        return redirect(url_for('admin_bp.list_admin_users'))

    if request.method == 'POST':
        # The POST logic for saving assignments remains the same and is correct.
        try:
            current_assignments = auth_manager.get_assigned_grade_sections_for_teacher(teacher_user_id)
            submitted_assignments = set()
            for key in request.form:
                if key.startswith('assignment_'):
                    try:
                        parts = key.split('_')
                        grade_id = int(parts[1])
                        section_letter = parts[2].upper()
                        submitted_assignments.add((grade_id, section_letter))
                    except (IndexError, ValueError, TypeError):
                        current_app.logger.warning(f"Could not parse assignment key: {key}")

            assignments_to_add = submitted_assignments - current_assignments
            assignments_to_remove = current_assignments - submitted_assignments
            errors = False
            for grade_id, section_letter in assignments_to_add:
                if not auth_manager.assign_teacher_to_grade_section(teacher_user_id, grade_id, section_letter):
                    errors = True
                    flash(f"Failed to assign G:{grade_id}/S:{section_letter}.", "error")
            
            for grade_id, section_letter in assignments_to_remove:
                if not auth_manager.unassign_teacher_from_grade_section(teacher_user_id, grade_id, section_letter):
                    errors = True
                    flash(f"Failed to unassign G:{grade_id}/S:{section_letter}.", "error")

            if not errors:
                flash(f"Assignments updated for {teacher['username']}.", "success")
            else:
                flash("Some errors occurred updating assignments.", "warning")
        except Exception as e:
            current_app.logger.error(f"Error processing teacher assignments for T:{teacher_user_id}: {e}")
            flash("An unexpected error occurred.", "danger")
        return redirect(url_for('admin_bp.list_admin_users'))

    # --- THIS IS THE FIX FOR THE GET REQUEST ---
    # We now fetch grades and explicitly get the existing sections for each one.
    all_grades_structured = defaultdict(lambda: defaultdict(list))
    assigned_grade_sections = set()
    try:
        all_grades = student_manager.get_all_grades_for_selection()
        for grade in all_grades:
            # For each grade, fetch the sections that have been created for it.
            grade['sections'] = student_manager.get_sections_for_grade(grade['grade_id'])
            
            subject_name = grade.get('subject_name', 'Uncategorized Subject')
            category_name = grade.get('category_name', 'Uncategorized Category')
            all_grades_structured[subject_name][category_name].append(grade)
            
        assigned_grade_sections = auth_manager.get_assigned_grade_sections_for_teacher(teacher_user_id)
    except Exception as e:
        current_app.logger.error(f"Error fetching data for teacher assignment page T:{teacher_user_id}: {e}")
        flash("Error loading data for assignment page.", "danger")
        
    return render_template('admin_manage_teacher_assignments.html',
                           teacher=teacher,
                           structured_grades=all_grades_structured,
                           assigned_grade_sections=assigned_grade_sections)


# --- Student Record Management (Admin Perspective) ---
@admin_bp.route('/students') # Original: /students (global)
@login_required
@admin_required # Admins see all, teachers have a similar route in teacher_bp for their students
def list_students():
    search_term = request.args.get('search', '').strip()
    students = []
    try:
        # Admin gets all students
        students = student_manager.get_all_students(search_term=search_term if search_term else None)
        for student in students:
            created_at_str = student.get('created_at')
            try:
                student['created_at_formatted'] = datetime.datetime.fromisoformat(created_at_str).strftime('%Y-%m-%d') if created_at_str else "N/A"
            except (ValueError, TypeError):
                student['created_at_formatted'] = created_at_str
    except Exception as e:
        current_app.logger.error(f"Error fetching students for admin web view: {e}")
        flash("Error retrieving student list.", "error")
        students = []
    return render_template('students_list.html', # This template might need to adapt or be admin-specific
                           students=students,
                           search_term=search_term,
                           user_role=current_user.role)

@admin_bp.route('/student/<int:student_id>') # Original: /student/<id> (global)
@login_required
@admin_required # Admins can view any student
def view_student(student_id):
    student_data = None # Renamed from student
    progress = []
    history = []
    assignment_details = None
    quiz_attempts = []
    task_submissions = []
    assigned_teachers_list = [] # Renamed from assigned_teachers

    try:
        student_data = student_manager.get_student(student_id)
        if not student_data:
            flash(f"Student with ID {student_id} not found.", "error")
            return redirect(url_for('admin_bp.list_students'))
        student_data = dict(student_data)

        if hasattr(student_manager, 'get_student_current_assignment_details'):
            assignment_details = student_manager.get_student_current_assignment_details(student_id)
        else:
            current_app.logger.warning("get_student_current_assignment_details helper missing!")

        progress = student_manager.get_student_memorization_progress(student_id)
        history = student_manager.get_student_recitation_history(student_id)

        if hasattr(student_manager, 'get_quiz_attempts_for_student'):
            quiz_attempts = student_manager.get_quiz_attempts_for_student(student_id)
        else:
            current_app.logger.warning("get_quiz_attempts_for_student helper missing!")

        if hasattr(student_manager, 'get_task_submissions_for_student'):
            task_submissions = student_manager.get_task_submissions_for_student(student_id)
        else:
            current_app.logger.warning("get_task_submissions_for_student helper missing!")

        if hasattr(auth_manager, 'get_teachers_for_student'): # Directly assigned
            assigned_teachers_list = auth_manager.get_teachers_for_student(student_id)
        else:
            current_app.logger.warning("auth_manager.get_teachers_for_student helper missing!")
    except Exception as e:
        current_app.logger.error(f"Error fetching student details view for {student_id} (admin): {e}")
        traceback.print_exc()
        flash("Error loading some student details.", "warning")

    return render_template('student_detail.html', # This template might need adaptation
                           student=student_data,
                           progress=progress,
                           history=history,
                           assignment=assignment_details,
                           quiz_attempts=quiz_attempts,
                           task_submissions=task_submissions,
                           assigned_teachers=assigned_teachers_list,
                           status_options=getattr(student_manager, 'STATUS_OPTIONS', []),
                           quality_options=getattr(student_manager, 'QUALITY_OPTIONS', []))

# add_student route (from user's provided app.py, slightly modified)
# This route allows admin/teacher.
@admin_bp.route('/students/add-record', methods=['GET', 'POST']) # Original path was /students/add
@login_required
# No @admin_required, internal check for admin or teacher
def add_student_record(): # Renamed to avoid conflict if student_bp has an add_student
    if not hasattr(current_user, 'role') or current_user.role not in ['admin', 'teacher']:
        flash("You do not have permission to add student records.", "error")
        return redirect(url_for('main_bp.index')) # Or admin_bp.dashboard / teacher_bp.dashboard

    # Consider using a WTForm: AddStudentSimpleForm()
    if request.method == 'POST':
        name = request.form.get('name')
        contact = request.form.get('contact')
        grade_level_str = request.form.get('grade_level')
        grade_level = int(grade_level_str) if grade_level_str and grade_level_str.isdigit() else None

        if not name or not name.strip():
            flash('Student name is required.', 'error')
            return render_template('add_student.html', name=name, contact_info=contact, grade_level=grade_level_str)

        student_id_val = student_manager.add_student(name, contact if contact else None, grade_level=grade_level) # Renamed student_id
        if student_id_val:
            flash(f'Student record "{name}" added successfully!', 'success')
            # Redirect to the appropriate student list based on role
            if current_user.role == 'admin':
                return redirect(url_for('admin_bp.list_students'))
            else: # Teacher
                return redirect(url_for('teacher_bp.list_students'))
        else:
            flash('Failed to add student record.', 'error')
            return render_template('add_student.html', name=name, contact_info=contact, grade_level=grade_level_str)
    return render_template('add_student.html')


@admin_bp.route('/student/<int:student_id>/edit-record', methods=['GET', 'POST']) # Original: /student/<id>/edit
@login_required
@admin_required # Only admins edit student records directly
def edit_student_record(student_id): # Renamed from edit_student
    student_data = student_manager.get_student(student_id) # Renamed from student
    if not student_data:
        abort(404)
    form = EditStudentForm(request.form, data=student_data if request.method == 'GET' else None)
    if form.validate_on_submit(): # Checks method POST
        new_name = form.name.data
        new_contact = form.contact_info.data if form.contact_info.data else None
        grade_level_str = form.grade_level.data
        new_grade_level = int(grade_level_str) if grade_level_str else None
        if student_manager.update_student(student_id, name=new_name, contact_info=new_contact, grade_level=new_grade_level):
            flash('Student information updated successfully!', 'success')
            return redirect(url_for('admin_bp.view_student', student_id=student_id))
        else:
            flash('Failed to update student information.', 'error')
    return render_template('edit_student.html', form=form, student=student_data)

@admin_bp.route('/student/<int:student_id>/delete-record', methods=['POST']) # Original: /student/<id>/delete
@login_required
@admin_required
def delete_student_record(student_id): # Renamed from delete_student
    student_data = student_manager.get_student(student_id) # Renamed from student
    if not student_data:
        flash(f"Student with ID {student_id} not found.", "error")
    else:
        student_name = student_data['name']
        if student_manager.delete_student(student_id):
            flash(f'Student record "{student_name}" (ID: {student_id}) deleted successfully!', 'success')
        else:
            flash(f'Failed to delete student record "{student_name}" (ID: {student_id}).', 'error')
    return redirect(url_for('admin_bp.list_students'))


@admin_bp.route('/student/<int:student_id>/edit_assignment', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_student_assignment(student_id):
    student_data = student_manager.get_student(student_id) # Renamed from student
    if not student_data:
        flash(f"Student with ID {student_id} not found.", "error")
        return redirect(url_for('admin_bp.list_admin_users'))
    form = EditStudentAssignmentForm()
    current_assignment = None
    try:
        if hasattr(student_manager, 'get_student_current_assignment_details'):
            current_assignment = student_manager.get_student_current_assignment_details(student_id)
            current_app.logger.debug(f"Current assignment for student {student_id}: {current_assignment}")
        else:
            current_app.logger.warning("get_student_current_assignment_details helper missing!")
    except Exception as e:
        current_app.logger.error(f"Error getting current assignment details: {e}")
        flash("Could not load current assignment details.", "warning")

    try:
        all_subjects = student_manager.get_all_subjects()
        form.subject_id.choices = [(s['subject_id'], s['subject_name']) for s in all_subjects]
        form.subject_id.choices.insert(0, ('0', '-- Select Subject --')) # '0' or ''
    except Exception as e:
        current_app.logger.error(f"Error populating subject choices: {e}")
        flash("Could not load subject list.", "error")
        form.subject_id.choices = [('', '-- Error --')]
    # Grade/Section choices are populated by JS or on POST validation

    if request.method == 'POST': # Repopulate choices if validation fails
        submitted_subject_id_str = request.form.get('subject_id')
        if submitted_subject_id_str and submitted_subject_id_str != '0':
            try:
                submitted_subject_id = int(submitted_subject_id_str)
                grades_for_subject = student_manager.get_grades_for_subject(submitted_subject_id)
                form.grade_id.choices = [(g['grade_id'], f"{g.get('category_name','')} / {g['grade_name']}") for g in grades_for_subject]
                form.grade_id.choices.insert(0, ('', '-- Select Grade --'))
            except (ValueError, TypeError, Exception) as e:
                 current_app.logger.error(f"Error dynamically populating grade choices for edit_student_assignment POST: {e}")
                 form.grade_id.choices = [('', '-- Error Loading Grades --')]
        else:
             form.grade_id.choices = [('', '-- Select Subject First --')]


    if form.validate_on_submit():
        try:
            new_grade_id = form.grade_id.data
            new_section_letter = form.section_letter.data
            if hasattr(student_manager, 'update_student_assignment'):
                success = student_manager.update_student_assignment(student_id, new_grade_id, new_section_letter)
                if success:
                    flash(f"Student {student_data['name']}'s assignment updated successfully!", "success")
                    return redirect(url_for('admin_bp.view_student', student_id=student_id))
                else:
                    flash("Failed to update student assignment in database.", "danger")
            else:
                flash("Update assignment function missing!", "error")
                current_app.logger.error("ERROR: student_manager.update_student_assignment function missing!")
        except Exception as e:
            current_app.logger.error(f"Error processing student assignment update for student {student_id}: {e}")
            traceback.print_exc()
            flash("An unexpected server error occurred while updating the assignment.", "danger")
    elif request.method == 'POST': # Validation failed
        flash('Please correct the errors shown.', 'warning')
        current_app.logger.debug(f"Form errors in edit_student_assignment: {form.errors}")


    return render_template('admin_edit_student_assignment.html',
                           form=form,
                           student=student_data,
                           current_assignment=current_assignment)

@admin_bp.route('/student/<int:student_id>/assign_teachers', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_assign_student_teachers(student_id):
    student_data = student_manager.get_student(student_id) # Renamed from student
    if not student_data:
        flash(f"Student with ID {student_id} not found.", "error")
        return redirect(url_for('admin_bp.list_admin_users'))
    form = AssignTeachersToStudentForm() # No request.form on GET

    if request.method == 'POST' and form.validate_on_submit(): # validate_on_submit handles POST check
        try:
            submitted_teacher_ids = set(request.form.getlist('teacher_ids', type=int))
            current_teacher_ids = auth_manager.get_assigned_teacher_ids_for_student(student_id)
            ids_to_add = submitted_teacher_ids - current_teacher_ids
            ids_to_remove = current_teacher_ids - submitted_teacher_ids
            errors = False
            for teacher_id in ids_to_add:
                if not auth_manager.assign_teacher_to_student(teacher_id, student_id, current_user.id):
                    errors = True; flash(f"Failed to assign teacher ID {teacher_id}.", "error")
            for teacher_id in ids_to_remove:
                if not auth_manager.unassign_teacher_from_student(teacher_id, student_id):
                    errors = True; flash(f"Failed to unassign teacher ID {teacher_id}.", "error")
            if not errors:
                flash(f"Teacher assignments updated successfully for {student_data['name']}.", "success")
            else:
                flash("Some errors occurred updating teacher assignments.", "warning")
        except Exception as e:
            current_app.logger.error(f"Error processing teacher assignments for student {student_id}: {e}")
            traceback.print_exc()
            flash("An unexpected error occurred processing assignments.", "danger")
        return redirect(url_for('admin_bp.view_student', student_id=student_id))
    elif request.method == 'POST': # CSRF or other form validation fail
        flash('Form submission error. Please try again.', 'danger')

    # GET Request
    all_teachers_list = [] # Renamed from all_teachers
    assigned_teacher_ids_set = set() # Renamed from assigned_teacher_ids
    try:
        all_teachers_list = auth_manager.get_all_teachers()
        assigned_teacher_ids_set = auth_manager.get_assigned_teacher_ids_for_student(student_id)
    except Exception as e:
        current_app.logger.error(f"Error fetching data for student-teacher assignment form (Student {student_id}): {e}")
        flash("Error loading data for assignment page.", "danger")
    return render_template('admin_assign_student_teachers.html',
                           form=form,
                           student=student_data,
                           all_teachers=all_teachers_list,
                           assigned_teacher_ids=assigned_teacher_ids_set)


# --- Curriculum Structure Management (Subjects, Categories, Grades, Sections) ---
@admin_bp.route('/subjects', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_subjects():
    """Page to view and add new Subjects."""
    if request.method == 'POST':
        # This logic for adding a new subject remains the same
        subject_name = request.form.get('subject_name')
        if not subject_name or not subject_name.strip():
            flash("Subject Name cannot be empty.", "warning")
        else:
            if student_manager.add_subject(subject_name, request.form.get('description')):
                flash(f"Subject '{subject_name}' added successfully!", "success")
            else:
                flash(f"Failed to add subject '{subject_name}'. It may already exist.", "danger")
        return redirect(url_for('admin_bp.manage_subjects'))

    all_subjects = student_manager.get_all_subjects()
    return render_template('admin_subjects.html', subjects=all_subjects)






@admin_bp.route('/curriculum-manager') # <<< New, clear URL
@login_required
@admin_required
def curriculum_manager_page():
    """Renders the enhanced, modal-based interface for managing Subjects."""
    form = EditSubjectForm() 
    all_subjects = student_manager.get_all_subjects()
    
    return render_template(
        'admin_manage_subjects_enhanced.html', 
        subjects=all_subjects,
        form=form
    )



@admin_bp.route('/subject/<int:subject_id>/categories')
@login_required
@admin_required
def manage_categories_for_subject(subject_id):
    """Renders the enhanced, modal-based interface for managing Categories."""
    subject = student_manager.get_subject_by_id(subject_id)
    if not subject:
        flash("Subject not found.", "error")
        return redirect(url_for('admin_bp.curriculum_manager_page'))

    # The form for the Add/Edit Category modal
    form = EditCategoryForm()
    
    # Fetch all categories for this specific subject
    categories = student_manager.get_categories_for_subject(subject_id)
    
    # This route will use the 'admin_manage_categories_enhanced.html' template
    # that we designed in the previous step.
    return render_template(
        'admin_manage_categories_enhanced.html',
        subject=subject,
        categories=categories,
        form=form
    )




@admin_bp.route('/subject/<int:subject_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_subject(subject_id):
    """Handles editing an existing subject."""
    subject = student_manager.get_subject_by_id(subject_id)
    if not subject:
        flash("Subject not found.", "error")
        return redirect(url_for('admin_bp.manage_subjects'))

    form = EditSubjectForm(request.form)

    if form.validate_on_submit():
        if student_manager.update_subject(subject_id, form.subject_name.data, form.description.data):
            flash(f"Subject '{form.subject_name.data}' updated successfully!", "success")
        else:
            flash("Error updating subject. The name may already exist.", "danger")
        return redirect(url_for('admin_bp.manage_subjects'))
    
    # On GET request, populate the form with existing data
    if request.method == 'GET':
        form.subject_name.data = subject['subject_name']
        form.description.data = subject['description']

    return render_template('edit_subject.html', form=form, subject=subject)



@admin_bp.route('/subject/<int:subject_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_subject_route(subject_id):
    """Handles the deletion of a subject and all its children data."""
    subject = student_manager.get_subject_by_id(subject_id)
    subject_name = subject['subject_name'] if subject else f"ID {subject_id}"

    # The ON DELETE CASCADE in the database will handle removing related items
    if student_manager.delete_subject(subject_id):
        flash(f"Subject '{subject_name}' and all its categories/grades were deleted.", "success")
    else:
        flash(f"Error deleting subject '{subject_name}'.", "danger")
    
    return redirect(url_for('admin_bp.manage_subjects'))




@admin_bp.route('/subject/<int:subject_id>/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_categories(subject_id):
    subject_data = student_manager.get_subject_by_id(subject_id) # Renamed from subject
    if not subject_data:
        flash(f"Subject with ID {subject_id} not found.", "warning")
        return redirect(url_for('admin_bp.manage_subjects'))
    if request.method == 'POST':
        category_name = request.form.get('category_name')
        description = request.form.get('description')
        if not category_name or not category_name.strip():
            flash("Category Name cannot be empty.", "warning")
        else:
            new_category_id = student_manager.add_category(subject_id, category_name, description)
            if new_category_id:
                flash(f"Category '{category_name}' added successfully to {subject_data['subject_name']}!", "success")
            else:
                flash(f"Failed to add category '{category_name}'. Does it already exist in this subject?", "danger")
        return redirect(url_for('admin_bp.manage_categories', subject_id=subject_id))
    categories_list_data = [] # Renamed from categories_list
    try:
        categories_list_data = student_manager.get_categories_for_subject(subject_id)
    except Exception as e:
        current_app.logger.error(f"Error fetching categories for subject {subject_id}: {e}")
        flash("Error retrieving category list.", "danger")
    return render_template('admin_categories.html', subject=subject_data, categories=categories_list_data)

@admin_bp.route('/category/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_category(category_id):
    category_data = student_manager.get_category_by_id(category_id) # Renamed from category
    if not category_data:
        flash(f"Category with ID {category_id} not found.", "error")
        return redirect(url_for('admin_bp.manage_subjects'))
    subject_data = student_manager.get_subject_by_id(category_data['subject_id']) # Renamed from subject
    if not subject_data:
        flash(f"Parent subject (ID: {category_data.get('subject_id','?')}) not found for category.", "error")
        return redirect(url_for('admin_bp.manage_subjects'))
    form = EditCategoryForm(request.form if request.method == 'POST' else None)
    if request.method == 'POST' and form.validate_on_submit():
        new_name = form.category_name.data
        new_description = form.description.data
        if student_manager.update_category(category_id, new_name, new_description):
            flash(f"Category '{new_name}' updated successfully!", "success")
            return redirect(url_for('admin_bp.manage_categories', subject_id=subject_data['subject_id']))
        else:
            flash(f"Failed to update category '{new_name}'. Name might already exist in this subject.", "danger")
    elif request.method == 'GET':
        form.process(data=category_data)
    return render_template('edit_category.html', form=form, category=category_data, subject=subject_data)

@admin_bp.route('/category/<int:category_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_category_route(category_id):
    category_data = student_manager.get_category_by_id(category_id) # Renamed from category
    category_name = category_data['category_name'] if category_data else f"ID {category_id}"
    subject_id_val = category_data['subject_id'] if category_data else None # Renamed from subject_id
    if student_manager.delete_category(category_id):
        flash(f"Category '{category_name}' and ALL its associated grades/sections/assignments deleted successfully!", 'success')
    else:
        flash(f"Failed to delete Category '{category_name}'. Check server logs.", 'danger')
    if subject_id_val:
        return redirect(url_for('admin_bp.manage_categories', subject_id=subject_id_val))
    else:
        return redirect(url_for('admin_bp.manage_subjects'))

@admin_bp.route('/category/<int:category_id>/grades', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_grades_for_category(category_id):
    """Page to view and add Grades for a specific Category."""
    category = student_manager.get_category_by_id(category_id)
    if not category:
        flash("Category not found.", "error")
        return redirect(url_for('admin_bp.manage_subjects'))
    
    subject = student_manager.get_subject_by_id(category['subject_id'])
    
    # --- VVV THIS IS THE FIX VVV ---
    # Create an instance of the form to pass to the template
    form = EditGradeForm(request.form)

    if request.method == 'POST' and form.validate_on_submit(): # Changed to check form validation
        grade_name = form.grade_name.data # Use form data
        description = form.description.data
        if student_manager.add_grade(category_id, grade_name, description):
            flash(f"Grade '{grade_name}' added successfully!", "success")
        else:
            flash(f"Failed to add grade '{grade_name}'.", "danger")
        return redirect(url_for('admin_bp.manage_grades_for_category', category_id=category_id))

    grades = student_manager.get_grades_for_category(category_id)
    
    # Pass the 'form' object to the template
    return render_template(
        'admin_manage_grades.html', 
        grades=grades, 
        category=category, 
        subject=subject, 
        form=form  # <<< ADD THIS
    )


@admin_bp.route('/grade/<int:grade_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_grade(grade_id):
    grade_data = student_manager.get_grade_by_id(grade_id) # Renamed from grade
    if not grade_data:
        flash(f"Grade with ID {grade_id} not found.", "error")
        return redirect(url_for('admin_bp.manage_subjects'))
    category_data = student_manager.get_category_by_id(grade_data['category_id']) # Renamed from category
    subject_data = student_manager.get_subject_by_id(category_data['subject_id']) if category_data else None # Renamed from subject
    if not category_data or not subject_data:
        flash("Could not load parent category/subject for the grade.", "error")
        return redirect(url_for('admin_bp.manage_subjects'))
    form = EditGradeForm(request.form if request.method == 'POST' else None)
    if request.method == 'POST' and form.validate_on_submit():
        new_name = form.grade_name.data
        new_description = form.description.data
        if student_manager.update_grade(grade_id, new_name, new_description):
            flash(f"Grade '{new_name}' updated successfully!", "success")
            return redirect(url_for('admin_bp.manage_category_grades', category_id=grade_data['category_id']))
        else:
            flash(f"Failed to update grade '{new_name}'. Name might already exist in this category.", "danger")
    elif request.method == 'GET':
        form.process(data=grade_data)
    return render_template('edit_grade.html', form=form, grade=grade_data, category=category_data, subject=subject_data)

@admin_bp.route('/grade/<int:grade_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_grade_route(grade_id):
    grade_data = student_manager.get_grade_by_id(grade_id) # Renamed from grade
    grade_name = grade_data['grade_name'] if grade_data else f"ID {grade_id}"
    category_id_val = grade_data['category_id'] if grade_data else None # Renamed from category_id
    if student_manager.delete_grade(grade_id):
        flash(f"Grade '{grade_name}' and its associated sections/assignments deleted successfully!", 'success')
    else:
        flash(f"Failed to delete Grade '{grade_name}'. Check server logs.", 'danger')
    if category_id_val:
        return redirect(url_for('admin_bp.manage_category_grades', category_id=category_id_val))
    else:
        return redirect(url_for('admin_bp.manage_subjects'))



# In src/blueprints/admin_bp.py

@admin_bp.route('/section/<int:section_id>/assign-students', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_section_students(section_id):
    """Page to assign students to a specific section."""
    section = student_manager.get_section_by_id(section_id)
    if not section:
        flash("Section not found.", "error")
        return redirect(url_for('admin_bp.curriculum_manager_page'))

    if request.method == 'POST':
        # Get the list of student IDs from the form checkboxes
        student_ids_to_assign = set(request.form.getlist('student_ids', type=int))
        
        # This logic is simplified. A more robust system would handle moving students
        # between sections. For now, we'll use a simplified update function.
        # This function will need to be created in the student_manager.
        
        # Let's assume a function that takes the section and the list of students.
        # This function needs to be written.
        # student_manager.set_students_for_section(section_id, student_ids_to_assign)
        
        # A simple model: Unassign all from this section, then re-assign the checked ones.
        # This is complex because of the UNIQUE constraint on student_id.
        # A better approach is to update each student's assignment individually.
        
        # Let's re-think the manager logic for simplicity.
        # The provided manager function 'update_student_assignments_for_section' will handle this.
        
        if student_manager.update_student_assignments_for_section(section_id, student_ids_to_assign):
            flash(f"Student assignments updated for Section {section['section_name']}.", "success")
        else:
            flash("An error occurred while updating assignments.", "danger")
            
        return redirect(url_for('admin_bp.manage_sections', grade_id=section['grade_id']))

    # For GET request:
    all_students = student_manager.get_all_students()
    assigned_student_ids = student_manager.get_assigned_student_ids_for_section(section_id)
    grade = student_manager.get_grade_by_id(section['grade_id'])
    
    return render_template(
        'admin_assign_section_students.html',
        section=section,
        grade=grade,
        all_students=all_students,
        assigned_student_ids=assigned_student_ids
    )

@admin_bp.route('/section/<int:section_id>/assign_teachers', methods=['GET', 'POST']) # Path updated from /assign
@login_required
@admin_required # Replaced manual check
def assign_section_teachers(section_id):
    section_data = student_manager.get_section_by_id(section_id) # Renamed from section
    if not section_data:
        flash(f"Section with ID {section_id} not found.", "warning")
        return redirect(url_for('admin_bp.manage_subjects'))
    grade_data = student_manager.get_grade_by_id(section_data['grade_id']) # Renamed from grade
    if not grade_data:
        flash(f"Grade associated with section ID {section_id} not found.", "warning")
        return redirect(url_for('admin_bp.manage_subjects'))

    if request.method == 'POST':
        try:
            submitted_ids = set(request.form.getlist('teacher_ids', type=int))
            current_ids = auth_manager.get_assigned_teacher_ids_for_section(section_id)
            ids_to_add = submitted_ids - current_ids
            ids_to_remove = current_ids - submitted_ids
            errors = False
            for teacher_id_val in ids_to_add: # Renamed teacher_id
                if not auth_manager.assign_teacher_to_section(teacher_id_val, section_id):
                    errors = True; flash(f"Failed to assign teacher ID {teacher_id_val}.", "error")
            for teacher_id_val in ids_to_remove:
                if not auth_manager.unassign_teacher_from_section(teacher_id_val, section_id):
                    errors = True; flash(f"Failed to unassign teacher ID {teacher_id_val}.", "error")
            if not errors:
                flash(f"Teacher assignments updated successfully for Section '{section_data['section_name']}'.", "success")
            else:
                flash("Some errors occurred updating assignments. Check logs.", "warning")
        except Exception as e:
            current_app.logger.error(f"Error processing teacher assignments for section {section_id}: {e}")
            flash("An unexpected error occurred while processing assignments.", "danger")
        return redirect(url_for('admin_bp.manage_sections', grade_id=grade_data['grade_id']))

    all_teachers_list = [] # Renamed from all_teachers
    assigned_teacher_ids_set = set() # Renamed from assigned_teacher_ids
    try:
        all_teachers_list = auth_manager.get_all_teachers()
        assigned_teacher_ids_set = auth_manager.get_assigned_teacher_ids_for_section(section_id)
    except Exception as e:
        current_app.logger.error(f"Error fetching data for assignment form (Section {section_id}): {e}")
        flash("Error loading data for assignment page.", "danger")
    return render_template('admin_assign_teacher.html',
                           section=section_data,
                           grade=grade_data,
                           all_teachers=all_teachers_list,
                           currently_assigned_ids=assigned_teacher_ids_set)

@admin_bp.route('/grade/<int:grade_id>/students', methods=['GET'])
@login_required
@admin_required
def view_grade_students(grade_id):
    grade_data = student_manager.get_grade_by_id(grade_id) # Renamed from grade
    if not grade_data:
        flash(f"Grade with ID {grade_id} not found.", "warning")
        return redirect(url_for('admin_bp.manage_subjects'))
    category_data = student_manager.get_category_by_id(grade_data['category_id']) # Renamed from category
    subject_data = student_manager.get_subject_by_id(category_data['subject_id']) if category_data else None # Renamed from subject
    students_list_data = [] # Renamed from students_list
    try:
        students_list_data = student_manager.get_students_in_grade(grade_id)
    except Exception as e:
        current_app.logger.error(f"Error fetching students for grade {grade_id} page: {e}")
        flash("Error retrieving student list for this grade.", "danger")
    return render_template('admin_grade_students.html',
                           grade=grade_data,
                           category=category_data,
                           subject=subject_data,
                           students=students_list_data)

# --- Quiz and Question Bank Management (Admin) ---
@admin_bp.route('/quiz/questions', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_quiz_questions():
    form = AddQuizQuestionForm() # Your form from forms.py

    # --- Populate Subject Choices (Main Banks) ---
    try:
        all_subjects = student_manager.get_all_subjects()
        form.subject_id.choices = [('', '-- Select Main Bank (Subject)* --')] + \
                                  [(s['subject_id'], s['subject_name']) for s in all_subjects]
    except Exception as e:
        current_app.logger.error(f"Error populating subject choices for admin_manage_quiz_questions: {e}")
        flash("Could not load subject list for question banks.", "error")
        form.subject_id.choices = [('', '-- Error Loading Subjects --')]

    # --- Populate Category Choices (Sub-banks) ---
    # This handles re-population on POST if validation fails and a subject was chosen
    if request.method == 'POST':
        selected_subject_id_str = request.form.get('subject_id') # Get from raw form data
        if selected_subject_id_str:
            try:
                selected_subject_id = int(selected_subject_id_str)
                categories_for_subject = student_manager.get_categories_for_subject(selected_subject_id)
                form.category_id.choices = [('', '-- Select Category/Sub-bank* --')] + \
                                           [(c['category_id'], c['category_name']) for c in categories_for_subject]
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"Error populating category choices on POST for admin: {e}")
                form.category_id.choices = [('', '-- Error or Select Subject First --')]
        else:
            form.category_id.choices = [('', '-- Select Subject First --')]
    else: # For GET request
        form.category_id.choices = [('', '-- Select Subject First --')]

    # --- Populate Target Grade ID Choices (Admins see all grades) ---
    # This part of your existing admin_manage_quiz_questions logic should be similar
    grade_choices_admin = [('', '-- Optional: Assign to Specific Grade --')] # Renamed variable
    try:
        if hasattr(student_manager, 'get_all_grades_for_selection'):
            all_grades_admin = student_manager.get_all_grades_for_selection() # Renamed variable
            grade_choices_admin.extend([(g['grade_id'], f"{g['subject_name']}/{g['category_name']}/{g['grade_name']}") for g in all_grades_admin])
        else:
            current_app.logger.warning("Warning: get_all_grades_for_selection helper missing for admin questions!")
        form.target_grade_id.choices = grade_choices_admin
    except Exception as e:
        current_app.logger.error(f"Error populating all grade choices for admin: {e}")
        form.target_grade_id.choices = [('', '-- Error Loading Grades --')]

    # Repopulate target_grade_id choices on POST if validation fails (if not already covered by above)
    if request.method == 'POST' and not form.target_grade_id.choices: # defensive
        try:
            all_grades_post_admin = student_manager.get_all_grades_for_selection() # Renamed
            form.target_grade_id.choices = [('', '-- Optional: Assign to Specific Grade --')] + \
                                          [(g['grade_id'], f"{g['subject_name']}/{g['category_name']}/{g['grade_name']}") for g in all_grades_post_admin]
        except Exception as e_post_choices:
            current_app.logger.error(f"Error repopulating all grade choices on POST for admin: {e_post_choices}")


    if form.validate_on_submit():
        question_text = form.question_text.data
        topic = form.topic.data or None # This is the specific topic within the category
        question_type = form.question_type.data
        
        # --- Get the new category_id and the target_grade_id ---
        category_id_val = form.category_id.data # From the new field
        target_grade_id_val = form.target_grade_id.data # Optional from existing field

        options_text = [form.option_1.data, form.option_2.data, form.option_3.data, form.option_4.data]
        correct_mcq_index_str = form.correct_option.data
        correct_tf_answer = form.true_false_correct.data
        matching_pairs_data = form.matching_pairs.data
        
        validation_ok = True
        new_question_id = None
        options_to_add = []
        pairs_to_add = []

        # ... (Keep your existing logic for validating options/pairs based on question_type) ...
        # Example (ensure it matches your full existing validation logic for MCQ, TF, MATCHING):
        if question_type == 'MCQ':
            correct_mcq_index = int(correct_mcq_index_str) if correct_mc_index_str else 0
            # ... (full MCQ option validation) ...
            options_to_add = valid_options_mcq # after validation
        # ... (elif for TRUE_FALSE, MATCHING, WRITING) ...

        # Ensure category_id is selected (InputRequired on form should also catch this)
        if not category_id_val:
            form.category_id.errors.append("Please select a category/sub-bank for the question.")
            validation_ok = False
            
        if validation_ok:
            try:
                if hasattr(student_manager, 'add_quiz_question_with_options_and_pairs'):
                    new_question_id = student_manager.add_quiz_question_with_options_and_pairs(
                        question_text=question_text,
                        question_type=question_type,
                        topic=topic, # Specific topic
                        category_id=category_id_val, # --- PASS THE NEW category_id ---
                        created_by_user_id=current_user.id,
                        target_grade_id=target_grade_id_val, # Optional target grade
                        options_data=options_to_add,
                        pairs_data=pairs_to_add
                    )
                else:
                    flash("Backend function for adding question is missing.", "error")
                    raise Exception("add_quiz_question_with_options_and_pairs missing")

                if new_question_id:
                    flash(f"New {question_type} question added successfully to the selected category!", "success")
                    return redirect(url_for('admin_bp.manage_quiz_questions'))
                else:
                    flash("Failed to add quiz question. Please check details and ensure category is selected.", "danger")
            except ValueError as ve:
                flash(f"Invalid input: {ve}", "warning")
            except Exception as e:
                current_app.logger.error(f"Error processing admin add quiz question: {e}")
                traceback.print_exc()
                flash(f"An error occurred: {str(e)}", "danger")

    elif request.method == 'POST': # Validation failed
        flash("Please correct the errors shown in the form.", "warning")
        current_app.logger.debug(f"Admin AddQuizQuestionForm errors: {form.errors}")

    existing_questions_list = []
    try:
        # Consider enhancing get_all_quiz_questions_with_options to show category/subject
        if hasattr(student_manager, 'get_all_quiz_questions_with_options_and_pairs'):
            existing_questions_list = student_manager.get_all_quiz_questions_with_options_and_pairs() # Use the more comprehensive getter
        elif hasattr(student_manager, 'get_all_quiz_questions_with_options'):
             existing_questions_list = student_manager.get_all_quiz_questions_with_options()
        else:
            current_app.logger.warning("Warning: Helper to get existing questions missing!")
    except Exception as e:
        current_app.logger.error(f"Error fetching existing quiz questions for admin: {e}")
        flash("Error loading existing questions list.", "danger")
        
    return render_template('admin_manage_quiz.html', form=form, questions=existing_questions_list)


@admin_bp.route('/quiz/question/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_quiz_question(question_id):
    question_data = None # Renamed from question
    if hasattr(student_manager, 'get_quiz_question_with_options_and_pairs'): # Use new combined getter
        question_data = student_manager.get_quiz_question_with_options_and_pairs(question_id)
    if not question_data:
        flash(f"Quiz Question ID {question_id} not found.", "error")
        return redirect(url_for('admin_bp.manage_quiz_questions'))

    original_question_type = question_data.get('question_type', 'MCQ')
    # Pass original_question_type to form for conditional logic if needed, or handle in template
    form = EditQuizQuestionForm(request.form if request.method == 'POST' else None, obj=question_data if request.method == 'GET' else None)
    form.question_type.data = original_question_type # Explicitly set for display

    grade_choices = [('', '-- Optional: Assign to Specific Grade --')]
    try:
        if hasattr(student_manager, 'get_all_grades_for_selection'):
            all_grades = student_manager.get_all_grades_for_selection()
            grade_choices.extend([(g['grade_id'], f"{g['subject_name']}/{g['category_name']}/{g['grade_name']}") for g in all_grades])
        form.target_grade_id.choices = grade_choices
    except Exception as e:
        current_app.logger.error(f"Error populating grade choices for edit_quiz_question: {e}")
        form.target_grade_id.choices = [('', '-- Error --')]

    if request.method == 'POST': # Repopulate choices if validation fails
        try:
            all_grades_post = student_manager.get_all_grades_for_selection()
            form.target_grade_id.choices = [('', '-- Optional: Assign to Specific Grade --')] + \
                                       [(g['grade_id'], f"{g['subject_name']}/{g['category_name']}/{g['grade_name']}") for g in all_grades_post]
        except Exception as e_post_choices:
             current_app.logger.error(f"Error repopulating grade choices on POST for edit_quiz_question: {e_post_choices}")


    if form.validate_on_submit():
        new_question_text = form.question_text.data
        new_topic = form.topic.data or None
        target_grade_id_str = form.target_grade_id.data
        new_target_grade_id = int(target_grade_id_str) if target_grade_id_str else None
        
        options_to_update = []
        pairs_to_update = []
        validation_ok = True

        if original_question_type == 'MCQ':
            options_text = [form.option_1.data, form.option_2.data, form.option_3.data, form.option_4.data]
            correct_mcq_index_str = form.correct_option.data # String '1', '2' etc.
            correct_mcq_index = int(correct_mcq_index_str) if correct_mcq_index_str else 0
            
            current_options = question_data.get('options', [])
            for i, text_content in enumerate(options_text):
                if text_content and text_content.strip():
                    option_id = current_options[i]['option_id'] if i < len(current_options) and 'option_id' in current_options[i] else None
                    options_to_update.append({
                        'option_id': option_id, # Keep existing ID if present, for update
                        'text': text_content.strip(),
                        'is_correct': (i + 1) == correct_mcq_index
                    })
            if len(options_to_update) < 2: flash("MCQ requires at least two options.", "warning"); validation_ok = False
            elif not any(opt['is_correct'] for opt in options_to_update): flash("MCQ correct answer is invalid.", "warning"); validation_ok = False
        
        elif original_question_type == 'TRUE_FALSE':
            correct_tf_answer = form.true_false_correct.data # 'True' or 'False'
            if not correct_tf_answer: flash("Select True or False.", "warning"); validation_ok = False
            else:
                current_options = question_data.get('options', [])
                options_to_update = [
                    {'option_id': current_options[0].get('option_id') if len(current_options)>0 else None, 'text': "True", 'is_correct': correct_tf_answer == 'True'},
                    {'option_id': current_options[1].get('option_id') if len(current_options)>1 else None, 'text': "False", 'is_correct': correct_tf_answer == 'False'}
                ]

        elif original_question_type == 'MATCHING':
            current_pairs = question_data.get('pairs', [])
            for i, pair_data_form in enumerate(form.matching_pairs.data):
                prompt = pair_data_form.get('prompt', '').strip()
                answer = pair_data_form.get('answer', '').strip()
                if prompt and answer:
                    pair_id = current_pairs[i]['pair_id'] if i < len(current_pairs) and 'pair_id' in current_pairs[i] else None
                    pairs_to_update.append({'pair_id': pair_id, 'prompt': prompt, 'answer': answer})
            if len(pairs_to_update) < 2: flash("Matching questions require at least two complete pairs.", "warning"); validation_ok = False
        
        # WRITING type has no options/pairs to update beyond text/topic/grade

        if validation_ok:
            if hasattr(student_manager, 'update_quiz_question_with_options_and_pairs'):
                success = student_manager.update_quiz_question_with_options_and_pairs(
                    question_id=question_id,
                    question_text=new_question_text,
                    topic=new_topic,
                    target_grade_id=new_target_grade_id,
                    options_data=options_to_update, # For MCQ/TF
                    pairs_data=pairs_to_update      # For MATCHING
                    # No need to pass question_type, it's fixed for existing question
                )
                if success:
                    flash("Quiz question updated successfully!", "success")
                    return redirect(url_for('admin_bp.manage_quiz_questions'))
                else:
                    flash("Failed to update quiz question.", "danger")
            else:
                flash("Backend update function missing.", "error")
    elif request.method == 'POST': # Validation failed
        flash("Please correct the errors shown.", "warning")
        current_app.logger.debug(f"EditQuizQuestionForm errors: {form.errors}")

    # GET Request: Populate form from question_data
    if request.method == 'GET' and question_data:
        form.question_text.data = question_data.get('question_text')
        form.topic.data = question_data.get('topic')
        form.target_grade_id.data = str(question_data.get('target_grade_id')) if question_data.get('target_grade_id') else ''
        
        if original_question_type == 'MCQ':
            options = question_data.get('options', [])
            for i, option in enumerate(options):
                if i < 4: # Max 4 options in form
                    getattr(form, f'option_{i+1}').data = option.get('option_text')
                    if option.get('is_correct'):
                        form.correct_option.data = str(i+1) # SelectField expects string value
        elif original_question_type == 'TRUE_FALSE':
            options = question_data.get('options', [])
            for option in options:
                if option.get('is_correct'):
                    form.true_false_correct.data = option.get('option_text') # 'True' or 'False'
                    break
        elif original_question_type == 'MATCHING':
            # Populate FieldList for matching pairs
            form.matching_pairs.entries = [] # Clear existing entries if any
            for pair in question_data.get('pairs', []):
                form.matching_pairs.append_entry(pair)


    return render_template('edit_quiz_question.html', form=form, question=question_data, question_type=original_question_type)


@admin_bp.route('/quiz/question/<int:question_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_quiz_question_route(question_id):
    question_data = student_manager.get_quiz_question_with_options(question_id) # Renamed from question
    question_text = f"'{question_data['question_text'][:30]}...'" if question_data else f"ID {question_id}"
    if student_manager.delete_quiz_question(question_id):
        flash(f"Quiz Question {question_text} and its options/attempts deleted successfully!", 'success')
    else:
        flash(f"Failed to delete Quiz Question {question_text}. Check server logs.", 'danger')
    return redirect(url_for('admin_bp.manage_quiz_questions'))

@admin_bp.route('/quizzes', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_quizzes():
    manager = student_manager
    form = QuizForm(request.form if request.method == 'POST' else None)
    if form.validate_on_submit():
        title = form.title.data
        description = form.description.data
        is_active = form.is_active.data
        if hasattr(manager, 'add_quiz'):
            new_quiz_id = manager.add_quiz(
                title=title, description=description, is_active=is_active, created_by_user_id=current_user.id
            )
            if new_quiz_id:
                flash(f"Quiz '{title}' created successfully!", "success")
            else:
                flash(f"Failed to create quiz '{title}'. Title might already exist or DB error occurred.", "danger")
        else:
            flash("Backend function 'add_quiz' is missing!", "error")
        return redirect(url_for('admin_bp.manage_quizzes'))
    all_quizzes_list = [] # Renamed from all_quizzes
    try:
        if hasattr(manager, 'get_all_quizzes'):
            all_quizzes_list = manager.get_all_quizzes(only_active=False)
        else:
            current_app.logger.warning("Warning: get_all_quizzes helper missing!")
            flash("Could not load existing quizzes list.", "warning")
    except Exception as e:
        current_app.logger.error(f"Error fetching quizzes for admin page: {e}")
        flash("Error retrieving quiz list.", "danger")
    return render_template('admin_manage_quizzes.html', quizzes=all_quizzes_list, form=form)

@admin_bp.route('/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_quiz(quiz_id):
    quiz_data = student_manager.get_quiz_by_id(quiz_id) # Renamed from quiz
    if not quiz_data:
        flash(f"Quiz with ID {quiz_id} not found.", "error")
        return redirect(url_for('admin_bp.manage_quizzes'))
    form = QuizForm(request.form if request.method == 'POST' else None)
    if form.validate_on_submit():
        title = form.title.data
        description = form.description.data
        is_active = form.is_active.data
        if hasattr(student_manager, 'update_quiz'):
            if student_manager.update_quiz(quiz_id, title, description, is_active):
                flash(f"Quiz '{title}' updated successfully!", "success")
                return redirect(url_for('admin_bp.manage_quizzes'))
            else:
                flash(f"Failed to update quiz '{title}'. Title might already exist or DB error.", "danger")
        else:
            flash("Backend function 'update_quiz' missing!", "error")
    elif request.method == 'GET':
        form_data = {
            'title': quiz_data.get('title'),
            'description': quiz_data.get('description'),
            'is_active': quiz_data.get('is_active', True)
        }
        form.process(data=form_data)
    return render_template('edit_quiz.html', form=form, quiz=quiz_data)

@admin_bp.route('/quiz/<int:quiz_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_quiz_route(quiz_id):
    quiz_data = student_manager.get_quiz_by_id(quiz_id) # Renamed from quiz
    quiz_title = quiz_data['title'] if quiz_data else f"ID {quiz_id}"
    if hasattr(student_manager, 'delete_quiz'):
        if student_manager.delete_quiz(quiz_id):
            flash(f"Quiz '{quiz_title}' and its question assignments deleted successfully! Attempt history retained.", 'success')
        else:
            flash(f"Failed to delete Quiz '{quiz_title}'. Check server logs.", 'danger')
    else:
        flash("Backend function 'delete_quiz' is missing!", "error")
        current_app.logger.error("ERROR: student_manager.delete_quiz function not found!")
    return redirect(url_for('admin_bp.manage_quizzes'))

@admin_bp.route('/quiz/<int:quiz_id>/assign_questions', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_quiz_questions(quiz_id):
    quiz_data = None # Renamed from quiz
    if hasattr(student_manager, 'get_quiz_by_id'):
        quiz_data = student_manager.get_quiz_by_id(quiz_id)
    else:
        current_app.logger.warning("Warning: get_quiz_by_id helper missing!")
    if not quiz_data:
        flash(f"Quiz with ID {quiz_id} not found.", "warning")
        return redirect(url_for('admin_bp.manage_quizzes'))

    if request.method == 'POST':
        try:
            submitted_question_ids = set(request.form.getlist('question_ids', type=int))
            current_question_ids = student_manager.get_assigned_question_ids_for_quiz(quiz_id)
            ids_to_add = submitted_question_ids - current_question_ids
            ids_to_remove = current_question_ids - submitted_question_ids
            errors = False
            for question_id_val in ids_to_add: # Renamed question_id
                if not student_manager.assign_question_to_quiz(quiz_id, question_id_val):
                    errors = True; flash(f"Failed to assign question ID {question_id_val}.", "error")
            for question_id_val in ids_to_remove:
                if not student_manager.unassign_question_from_quiz(quiz_id, question_id_val):
                    errors = True; flash(f"Failed to unassign question ID {question_id_val}.", "error")
            if not errors:
                flash(f"Question assignments updated successfully for Quiz '{quiz_data['title']}'.", "success")
            else:
                flash("Some errors occurred updating question assignments.", "warning")
        except Exception as e:
            current_app.logger.error(f"Error processing question assignments for quiz {quiz_id}: {e}")
            traceback.print_exc()
            flash("An unexpected error occurred while processing assignments.", "danger")
        return redirect(url_for('admin_bp.manage_quizzes')) # Stay on admin quiz mgmt

    all_questions_list = [] # Renamed from all_questions
    assigned_question_ids_set = set() # Renamed from assigned_question_ids
    try:
        if hasattr(student_manager, 'get_all_questions_for_assignment'):
            all_questions_list = student_manager.get_all_questions_for_assignment()
        else:
            current_app.logger.warning("Warning: get_all_questions_for_assignment missing!")
        if hasattr(student_manager, 'get_assigned_question_ids_for_quiz'):
            assigned_question_ids_set = student_manager.get_assigned_question_ids_for_quiz(quiz_id)
        else:
            current_app.logger.warning("Warning: get_assigned_question_ids_for_quiz missing!")
    except Exception as e:
        current_app.logger.error(f"Error fetching data for quiz assignment form (Quiz {quiz_id}): {e}")
        flash("Error loading data for assignment page.", "danger")
    form_action_url = url_for('admin_bp.assign_quiz_questions', quiz_id=quiz_id)
    return render_template('admin_assign_quiz_questions.html',
                           quiz=quiz_data,
                           all_questions=all_questions_list,
                           assigned_question_ids=assigned_question_ids_set,
                           form_action_url=form_action_url)

# --- Game Content Management (Admin) ---
@admin_bp.route('/games/memory_match_pairs', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_manage_memory_pairs():
    manager = student_manager
    form = AddMemoryPairForm(request.form if request.method == 'POST' else None)
    if form.validate_on_submit():
        category = form.category.data
        item1 = form.item1_text.data
        item2 = form.item2_text.data
        difficulty = form.difficulty.data
        is_active = form.is_active.data
        if hasattr(manager, 'add_memory_match_pair'):
            new_pair_id = manager.add_memory_match_pair(
                category=category, item1_text=item1, item2_text=item2,
                difficulty=difficulty, is_active=is_active, created_by_user_id=current_user.id
            )
            if new_pair_id:
                flash(f"Memory match pair '{item1} / {item2}' added successfully!", "success")
            else:
                flash("Failed to add memory match pair. Check logs.", "danger")
        else:
            flash("Backend function 'add_memory_match_pair' is missing!", "error")
        return redirect(url_for('admin_bp.admin_manage_memory_pairs'))
    all_pairs_list = [] # Renamed from all_pairs
    try:
        if hasattr(manager, 'get_all_memory_match_pairs'):
            all_pairs_list = manager.get_all_memory_match_pairs()
        else:
            current_app.logger.warning("Warning: get_all_memory_match_pairs helper missing!")
            flash("Could not load existing pairs list.", "warning")
    except Exception as e:
        current_app.logger.error(f"Error fetching memory pairs for admin page: {e}")
        flash("Error retrieving pairs list.", "danger")
    pairs_by_category_dict = defaultdict(list) # Renamed from pairs_by_category
    for pair in all_pairs_list:
        pairs_by_category_dict[pair.get('category', 'Uncategorized')].append(pair)
    return render_template('admin_manage_memory_pairs.html',
                           pairs_by_category=pairs_by_category_dict,
                           form=form)

# --- Announcement Management (Admin) ---
@admin_bp.route('/announcements')
@login_required
@admin_required
def admin_manage_announcements():
    all_announcements_list = [] # Renamed from all_announcements
    try:
        if hasattr(auth_manager, 'get_all_announcements'):
            all_announcements_list = auth_manager.get_all_announcements()
        else:
            current_app.logger.error("ERROR: auth_manager.get_all_announcements function missing!")
            flash("Could not load announcement list (server error).", "error")
    except Exception as e:
        current_app.logger.error(f"Error fetching all announcements for admin view: {e}")
        flash("Could not load announcement list.", "error")
    return render_template('admin_manage_announcements.html', announcements=all_announcements_list)

@admin_bp.route('/announcements/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_announcement():
    form = AnnouncementForm()
    grade_choices = [('', 'All Grades / Not Specific')]
    try:
        all_grades = student_manager.get_all_grades_for_selection()
        grade_choices.extend([(g['grade_id'], f"{g.get('subject_name','?')}/{g.get('category_name','?')}/{g.get('grade_name','?')}") for g in all_grades])
        form.target_grade_id.choices = grade_choices
    except Exception as e:
        current_app.logger.error(f"Error populating grade choices for announcement form: {e}")
        flash("Could not load grades for targeting.", "warning")
        form.target_grade_id.choices = [('', 'Error loading grades')]

    if request.method == 'POST': # Repopulate if validation fails
        try:
            all_grades_post = student_manager.get_all_grades_for_selection()
            form.target_grade_id.choices = [('', 'All Grades / Not Specific')] + [(g['grade_id'], f"{g.get('subject_name','?')}/{g.get('category_name','?')}/{g.get('grade_name','?')}") for g in all_grades_post]
        except:
            form.target_grade_id.choices = [('', 'Error loading grades')]

    if form.validate_on_submit():
        try:
            title = form.title.data
            content = form.content.data
            audience = form.audience_role.data
            grade_id_val = form.target_grade_id.data # Renamed from grade_id
            section = form.target_section_letter.data
            is_active = form.is_active.data
            section_to_save = section if grade_id_val and section else None
            if hasattr(auth_manager, 'create_announcement'):
                new_id = auth_manager.create_announcement(
                    creator_user_id=current_user.id, title=title, content=content,
                    audience_role=audience, target_grade_id=grade_id_val,
                    target_section_letter=section_to_save, is_active=is_active
                )
                if new_id:
                    flash(f"Announcement '{title}' created successfully!", "success")
                    return redirect(url_for('admin_bp.admin_manage_announcements'))
                else:
                    flash("Failed to create announcement. Check logs.", "danger")
            else:
                current_app.logger.error("ERROR: auth_manager.create_announcement function missing!")
                flash("Cannot create announcement (server error).", "error")
        except Exception as e:
            current_app.logger.error(f"Error processing add announcement form: {e}")
            flash("An unexpected error occurred while creating the announcement.", "danger")
    elif request.method == 'POST': # Validation failed
        flash("Please correct the errors below.", "warning")
    return render_template('announcement_form.html',
                           form=form,
                           form_title="Add New Announcement",
                           cancel_url=url_for('admin_bp.admin_manage_announcements'))

@admin_bp.route('/announcement/<int:announcement_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_announcement(announcement_id):
    announcement_data = auth_manager.get_announcement_by_id(announcement_id) # Renamed from announcement
    if not announcement_data:
        flash("Announcement not found.", "error")
        return redirect(url_for('admin_bp.admin_manage_announcements'))
    form = AnnouncementForm(request.form if request.method == 'POST' else None) # obj removed for manual population

    grade_choices = [('', 'All Grades / Not Specific')]
    try:
        all_grades = student_manager.get_all_grades_for_selection()
        grade_choices.extend([(g['grade_id'], f"{g.get('subject_name','?')}/{g.get('category_name','?')}/{g.get('grade_name','?')}") for g in all_grades])
        form.target_grade_id.choices = grade_choices
    except Exception as e:
        current_app.logger.error(f"Error populating grade choices for announcement form: {e}")
        form.target_grade_id.choices = [('', 'Error loading grades')]
    
    if request.method == 'POST': # Repopulate if validation fails
        try:
            all_grades_post = student_manager.get_all_grades_for_selection()
            form.target_grade_id.choices = [('', 'All Grades / Not Specific')] + [(g['grade_id'], f"{g.get('subject_name','?')}/{g.get('category_name','?')}/{g.get('grade_name','?')}") for g in all_grades_post]
        except:
            form.target_grade_id.choices = [('', 'Error loading grades')]


    if form.validate_on_submit():
        try:
            title = form.title.data
            content = form.content.data
            audience = form.audience_role.data
            grade_id_val = form.target_grade_id.data # Renamed from grade_id
            section = form.target_section_letter.data
            is_active = form.is_active.data
            section_to_save = section if grade_id_val and section else None
            if hasattr(auth_manager, 'update_announcement'):
                success = auth_manager.update_announcement(
                    announcement_id=announcement_id, title=title, content=content,
                    audience_role=audience, target_grade_id=grade_id_val,
                    target_section_letter=section_to_save, is_active=is_active
                )
                if success:
                    flash(f"Announcement '{title}' updated successfully!", "success")
                    return redirect(url_for('admin_bp.admin_manage_announcements'))
                else:
                    flash("Failed to update announcement. Check logs.", "danger")
            else:
                current_app.logger.error("ERROR: auth_manager.update_announcement function missing!")
                flash("Cannot update announcement (server error).", "error")
        except Exception as e:
            current_app.logger.error(f"Error processing edit announcement form: {e}")
            flash("An unexpected error occurred while updating the announcement.", "danger")
    elif request.method == 'GET': # Populate on GET
        form.title.data = announcement_data.get('title')
        form.content.data = announcement_data.get('content')
        form.audience_role.data = announcement_data.get('audience_role')
        form.target_grade_id.data = str(announcement_data.get('target_grade_id')) if announcement_data.get('target_grade_id') else ''
        form.target_section_letter.data = announcement_data.get('target_section_letter') or ''
        form.is_active.data = bool(announcement_data.get('is_active', True))
    elif request.method == 'POST': # Validation failed
        flash("Please correct the errors below.", "warning")

    return render_template('announcement_form.html',
                           form=form,
                           form_title=f"Edit Announcement (ID: {announcement_id})",
                           cancel_url=url_for('admin_bp.admin_manage_announcements'))

@admin_bp.route('/announcement/<int:announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_announcement(announcement_id):
    announcement_data = auth_manager.get_announcement_by_id(announcement_id) # Renamed from announcement
    announcement_title = announcement_data['title'] if announcement_data else f"ID {announcement_id}"
    if hasattr(auth_manager, 'delete_announcement'):
        if auth_manager.delete_announcement(announcement_id):
            flash(f"Announcement '{announcement_title}' deleted successfully!", 'success')
        else:
            flash(f"Failed to delete announcement '{announcement_title}'. It might not exist.", 'danger')
    else:
        current_app.logger.error("ERROR: auth_manager.delete_announcement function missing!")
        flash("Cannot delete announcement (server error).", "error")
    return redirect(url_for('admin_bp.admin_manage_announcements'))

# --- Attendance Viewing (Admin) ---
@admin_bp.route('/attendance/student/<int:student_id>')
@login_required
@admin_required
def admin_view_student_attendance(student_id):
    student_data = student_manager.get_student(student_id) # Renamed from student
    if not student_data:
        abort(404)
    attendance_summary_data = {} # Renamed from attendance_summary
    attendance_log_data = [] # Renamed from attendance_log
    try:
        attendance_summary_data = student_manager.get_attendance_summary_for_student(student_id)
        attendance_log_data = student_manager.get_attendance_for_student(student_id)
    except Exception as e:
        current_app.logger.error(f"Error loading attendance data for student {student_id} (Admin View): {e}")
        flash("An error occurred loading attendance data.", "danger")
    return render_template('view_student_attendance.html',
                           student=student_data,
                           summary=attendance_summary_data,
                           log=attendance_log_data,
                           viewer_role=current_user.role)

# This route was /admin/lessons/add in your last app.py example, it's already included above
# with the url_prefix making it /admin/lessons/add.
# def add_lesson_route(): ...
# --- Admin Lesson Management ---
@admin_bp.route('/lessons/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_lesson_route():
    form = AddLessonForm()
    
    # --- Populate Form Choices ---
    # This logic needs to run for GET requests and for POST if validation fails
    # to repopulate the form fields correctly.
    try:
        # Grades: Admins see all grades
        if hasattr(student_manager, 'get_all_grades_for_selection'):
            all_grades = student_manager.get_all_grades_for_selection()
            form.grade_id.choices = [(g['grade_id'], f"{g.get('subject_name','No Subject')} / {g.get('category_name','No Category')} / {g['grade_name']}") for g in all_grades]
        else:
            current_app.logger.warning("student_manager.get_all_grades_for_selection missing for admin add lesson.")
            form.grade_id.choices = []
        form.grade_id.choices.insert(0, ('', '-- Select Grade* --'))

        # Terms: Admins see all terms
        if hasattr(curriculum_manager, 'get_all_terms'):
            all_terms = curriculum_manager.get_all_terms()
            form.term_id.choices = [(t['term_id'], t['name']) for t in all_terms]
        else:
            current_app.logger.warning("curriculum_manager.get_all_terms missing for admin add lesson.")
            form.term_id.choices = []
        form.term_id.choices.insert(0, ('', '-- Select Term* --'))

        # Categories: Admins see all categories
        # Assuming a function like get_all_categories_for_selection or similar exists
        # Adjust if your student_manager has a different function for all categories.
        if hasattr(student_manager, 'get_all_categories_for_selection'): # You might need to create/verify this helper
            all_categories = student_manager.get_all_categories_for_selection()
            form.category_id.choices = [(c['category_id'], f"{c.get('subject_name','No Subject')} / {c['category_name']}") for c in all_categories]
        elif hasattr(student_manager, 'get_all_categories'): # Fallback if a simpler getter exists
             all_categories = student_manager.get_all_categories()
             form.category_id.choices = [(c['category_id'], c['category_name']) for c in all_categories]
        else:
            current_app.logger.warning("student_manager.get_all_categories_for_selection (or similar) missing for admin add lesson.")
            form.category_id.choices = []
        form.category_id.choices.insert(0, ('', '-- Select Category* --'))
        
        # Quizzes: Admins see all quizzes
        if hasattr(student_manager, 'get_all_quizzes'):
            all_quizzes = student_manager.get_all_quizzes(only_active=False) # Show all, active or not
            form.quiz_id.choices = [(q['quiz_id'], q['title']) for q in all_quizzes]
        else:
            current_app.logger.warning("student_manager.get_all_quizzes missing for admin add lesson.")
            form.quiz_id.choices = []
        form.quiz_id.choices.insert(0, ('', '-- Optional: Link Quiz --'))

        # Materials: Admins see all materials
        if hasattr(material_manager, 'get_materials'):
            all_materials = material_manager.get_materials()
            form.existing_material_ids.choices = [(m['material_id'], m.get('title') or m.get('filename_orig', f"Material ID {m['material_id']}")) for m in all_materials]
        else:
            current_app.logger.warning("material_manager.get_materials missing for admin add lesson.")
            form.existing_material_ids.choices = []

     # --- NEW SECTION TO POPULATE RUBRICS ---
        # For now, we fetch all rubrics from all subjects.
        # A future improvement could filter this with JavaScript based on the selected grade's subject.
        if hasattr(curriculum_manager, 'get_all_rubrics'): # Assumes a function to get ALL rubrics. Let's create it if needed.
             all_rubrics = curriculum_manager.get_all_rubrics()
             form.rubrics.choices = [(r['rubric_id'], f"{r['subject_name']}: {r['title']}") for r in all_rubrics]
        else:
            # If get_all_rubrics doesn't exist, we can build it from subjects.
            all_rubrics = []
            all_subjects = student_manager.get_all_subjects()
            for s in all_subjects:
                rubrics_for_s = curriculum_manager.get_rubrics_for_subject(s['subject_id'])
                for r in rubrics_for_s:
                    r['subject_name'] = s['subject_name'] # Add subject name for context
                    all_rubrics.append(r)
            form.rubrics.choices = [(r['rubric_id'], f"{r['subject_name']}: {r['title']}") for r in all_rubrics]
        # --- END OF NEW SECTION ---

    except Exception as e:
        current_app.logger.error(f"Error populating admin lesson form choices: {e}")
        traceback.print_exc()
        flash("Error loading dynamic choices for the lesson form. Some options might be unavailable.", "danger")
        # Set safe defaults if any previous choices failed
        if not hasattr(form.grade_id, 'choices') or not form.grade_id.choices:
            form.grade_id.choices = [('', '-- Error Loading Grades --')]
        if not hasattr(form.term_id, 'choices') or not form.term_id.choices:
            form.term_id.choices = [('', '-- Error Loading Terms --')]
        if not hasattr(form.category_id, 'choices') or not form.category_id.choices:
            form.category_id.choices = [('', '-- Error Loading Categories --')]
        if not hasattr(form.quiz_id, 'choices') or not form.quiz_id.choices:
            form.quiz_id.choices = [('', '-- Error Loading Quizzes --')]
        if not hasattr(form.existing_material_ids, 'choices') or not form.existing_material_ids.choices:
            form.existing_material_ids.choices = []


    if form.validate_on_submit():
        new_lesson_id = None
        final_material_ids_to_attach = set(form.existing_material_ids.data or [])

        try:
            # Handle new material upload
            uploaded_file_storage = form.new_material_upload.data
            if uploaded_file_storage and uploaded_file_storage.filename:
                if hasattr(material_manager, 'save_material'):
                    current_app.logger.debug(f"Admin uploading new file for lesson: {uploaded_file_storage.filename}")
                    newly_uploaded_material_id = material_manager.save_material(
                        uploader_user_id=current_user.id,  # Admin is the uploader
                        file_storage=uploaded_file_storage,
                        title=form.new_material_title.data or uploaded_file_storage.filename,
                        description=form.new_material_description.data
                    )
                    if newly_uploaded_material_id:
                        final_material_ids_to_attach.add(newly_uploaded_material_id)
                        flash(f"New material '{form.new_material_title.data or uploaded_file_storage.filename}' uploaded.", "info")
                    else:
                        flash("New material file upload failed. Lesson not created with this new material.", "warning")
                        # Decide if this is a hard stop or just a warning
                else:
                    flash("Material saving function is missing. Cannot upload new material.", "error")


            # Ensure required fields that might not be covered by basic WTForms validators are present
            if not all([form.grade_id.data, form.term_id.data, form.category_id.data, form.lesson_number.data, form.title.data]):
                 flash("Missing one or more required fields (Grade, Term, Category, Lesson Number, Title).", "danger")
                 raise ValueError("Missing required lesson fields for admin.")

            if hasattr(curriculum_manager, 'add_lesson'):
                new_lesson_id = curriculum_manager.add_lesson(
                    grade_id=form.grade_id.data,
                    term_id=form.term_id.data,
                    category_id=form.category_id.data,
                    lesson_number=form.lesson_number.data,
                    title=form.title.data,
                    creator_user_id=current_user.id, # Admin is the creator
                    summary=form.summary.data,
                    learning_outcomes=form.learning_outcomes.data,
                    mindmap_data=form.mindmap_data.data, # Assuming AddLessonForm has this field
                    quiz_id=form.quiz_id.data if form.quiz_id.data else None,
                    is_active=form.is_active.data,
                    unit_name=form.unit_name.data # Assuming AddLessonForm has this field
                )
            else:
                flash("Lesson creation function is missing. Cannot add lesson.", "error")
                raise Exception("curriculum_manager.add_lesson missing")

            if not new_lesson_id:
                if not get_flashed_messages(with_categories=True): # Avoid duplicate if add_lesson flashed
                    flash("Failed to create the lesson in the database. Lesson number might already exist for the selected grade/term/category.", "danger")
                raise Exception("Lesson database creation failed for admin.")


# --- NEW SECTION TO HANDLE RUBRIC TAGGING ---
            selected_rubric_ids = form.rubrics.data
            if selected_rubric_ids:
                if hasattr(curriculum_manager, 'update_lesson_rubrics'):
                    curriculum_manager.update_lesson_rubrics(new_lesson_id, selected_rubric_ids)
                    flash("Rubrics tagged successfully!", "info")
                else:
                    flash("Could not tag rubrics (backend function missing).", "warning")
            # --- END OF NEW SECTION ---

            # Attach materials if lesson creation was successful
            if final_material_ids_to_attach and hasattr(curriculum_manager, 'attach_material_to_lesson'):
                attachment_errors = False
                for material_id in final_material_ids_to_attach:
                    if not curriculum_manager.attach_material_to_lesson(new_lesson_id, material_id):
                        attachment_errors = True
                        current_app.logger.warning(f"Admin failed to attach material ID {material_id} to new lesson {new_lesson_id}.")
                if attachment_errors:
                    flash("Lesson created, but some selected materials failed to attach. Please manage attachments manually.", "warning")
                else:
                    flash(f"Lesson '{form.title.data}' created and materials attached successfully!", "success")
            elif final_material_ids_to_attach: # Materials selected but attach function missing
                 flash("Lesson created, but material attachment function is missing. Please assign materials manually.", "warning")
            else:
                flash(f"Lesson '{form.title.data}' created successfully (no materials attached).", "success")
            
            # Redirect to an admin view of the lesson or a list of all lessons
            return redirect(url_for('admin_bp.admin_view_lesson_details', lesson_id=new_lesson_id)) # Assuming such a route exists

        except Exception as e:
            current_app.logger.error(f"Error during admin lesson creation process: {e}")
            traceback.print_exc()
            if not get_flashed_messages(with_categories=True): # Avoid duplicate general error
                flash(f"An unexpected error occurred while creating the lesson: {str(e)}", "danger")
            # Form choices will be repopulated by the logic at the start of the function

    elif request.method == 'POST': # Validation failed
        flash("Please correct the errors highlighted in the form.", "warning")
        current_app.logger.debug(f"Admin AddLessonForm validation errors: {form.errors}")
        # Form choices will be repopulated by the logic at the start of the function

    # Render the template for GET requests or if POST validation failed
    return render_template('admin_add_lesson.html', 
                           form=form, 
                           form_title="Add New Lesson (Admin)",
                           cancel_url=url_for('admin_bp.admin_dashboard')) # Or a lesson list URL



# --- Reporting (Admin parts) ---
# These routes were global but admin-focused. If they become part of admin_bp,
# their paths will be /admin/reports, /admin/reports/student_summary etc.

@admin_bp.route('/reports')
@login_required
@admin_required # Assuming only admins access the main reports index from here
def reports_index():
    # Teachers might have their own reports index or a filtered view
    return render_template('reports_index.html',
                           status_options=getattr(student_manager, 'STATUS_OPTIONS', []),
                           quality_options=getattr(student_manager, 'QUALITY_OPTIONS', []))

@admin_bp.route('/reports/student_summary/<int:student_id>')
@login_required
@admin_required # Admins can view any student summary
def view_student_summary(student_id):
    try:
        report_content = reporting.generate_student_summary(student_id)
        report_title = f"Student Summary Report (ID: {student_id})"
        if report_content is None or (isinstance(report_content, str) and report_content.startswith("Error:")):
            flash(report_content or "Could not generate report.", "error")
            report_title = "Error Generating Report"
            report_content = "Could not generate report. Check student ID or logs."
    except Exception as e:
        current_app.logger.error(f"Error generating student summary report {student_id}: {e}")
        flash("An unexpected error occurred generating the report.", "danger")
        report_title, report_content = "Report Error", "Error generating report."
    return render_template('report_view.html', report_title=report_title, report_content=report_content)


@admin_bp.route('/reports/by_hifz_status')
@login_required
@admin_required # Admins see all statuses
def view_report_by_hifz_status():
    selected_status = request.args.get('status')
    if not selected_status or selected_status not in getattr(student_manager, 'STATUS_OPTIONS', []):
        flash("Invalid or missing Hifz status.", "warning")
        return redirect(url_for('admin_bp.reports_index'))
    try:
        # Admin report does not filter by teacher_id
        report_content = reporting.list_students_by_hifz_status(selected_status, teacher_id=None)
        report_title = f"Students with Hifz Status: {selected_status}"
        if not report_content or (isinstance(report_content, str) and "No students found" in report_content) :
            report_content = f"No students found with Hifz status '{selected_status}'."
    except Exception as e:
        current_app.logger.error(f"Error generating Hifz status report: {e}")
        flash("An unexpected error occurred generating the report.", "danger")
        report_title, report_content = "Report Error", "Error generating report."
    return render_template('report_view.html', report_title=report_title, report_content=report_content)

@admin_bp.route('/reports/by_recite_rating')
@login_required
@admin_required # Admins see all ratings
def view_report_by_recite_rating():
    selected_rating = request.args.get('rating')
    valid_ratings = set(opt for opt in getattr(student_manager, 'QUALITY_OPTIONS', []) if opt is not None)
    if selected_rating is None or selected_rating not in valid_ratings:
        flash("Invalid or missing Recitation rating.", "warning")
        return redirect(url_for('admin_bp.reports_index'))
    try:
        # Admin report does not filter by teacher_id
        report_content = reporting.list_students_by_recitation_rating(selected_rating, teacher_id=None)
        report_title = f"Students with Recitation Rating: {selected_rating}"
        if not report_content or (isinstance(report_content, str) and "No students found" in report_content):
            report_content = f"No students found with Recitation rating '{selected_rating}'."
    except Exception as e:
        current_app.logger.error(f"Error generating Recite rating report: {e}")
        flash("An unexpected error occurred generating the report.", "danger")
        report_title, report_content = "Report Error", "Error generating report."
    return render_template('report_view.html', report_title=report_title, report_content=report_content)

# Route for /attendance/section/view if admin has a specific version or if it's shared from main_bp
# For simplicity, admin might use the same /attendance/section/view as teachers but see all sections
# That logic would typically reside in a main_bp or a shared attendance_bp.
# If it is to be admin specific:
@admin_bp.route('/attendance/section/view')
@login_required
@admin_required
def admin_view_section_attendance_summary(): # Renamed to distinguish if shared route exists
    selected_grade_section = request.args.get('grade_section')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    assignment_choices = []
    # Admin sees all sections
    try:
        if hasattr(student_manager, 'get_all_grades_for_selection'):
            all_grades = student_manager.get_all_grades_for_selection()
            for grade_item in all_grades: # Renamed grade to grade_item
                grade_label_part = f"{grade_item.get('subject_name','?')}/{grade_item.get('category_name','?')}/{grade_item.get('grade_name','?')}"
                # TODO: Fetch actual sections for each grade instead of assuming A-E
                sections_for_grade = student_manager.get_sections_for_grade(grade_item['grade_id']) # You need this helper
                for sect in sections_for_grade: # Renamed section to sect
                    assignment_choices.append({
                        'value': f"{grade_item['grade_id']}_{sect['section_name']}", # Assuming section_name is 'A', 'B'
                        'label': f"{grade_label_part} - Section {sect['section_name']}"
                    })
            assignment_choices.sort(key=lambda x: x['label'])
        else:
            current_app.logger.warning("student_manager.get_all_grades_for_selection missing!")
    except Exception as e:
        current_app.logger.error(f"Error populating section choices for admin attendance view: {e}")

    summary_data = None
    detail_data = None
    if selected_grade_section:
        try:
            parts = selected_grade_section.split('_')
            selected_grade_id = int(parts[0])
            selected_section_letter = parts[1]
            if hasattr(student_manager, 'get_attendance_summary_for_section'):
                summary_data = student_manager.get_attendance_summary_for_section(
                    selected_grade_id, selected_section_letter, start_date_str, end_date_str
                )
            if hasattr(student_manager, 'get_attendance_detail_for_section'):
                detail_data = student_manager.get_attendance_detail_for_section(
                    selected_grade_id, selected_section_letter, start_date_str, end_date_str
                )
        except Exception as e_fetch:
            current_app.logger.error(f"Error fetching attendance data for section (admin): {e_fetch}")
            flash("An error occurred while fetching attendance data.", "danger")

    return render_template('view_section_attendance.html',
                           assignment_choices=assignment_choices,
                           selected_grade_section=selected_grade_section,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           summary_data=summary_data,
                           detail_data=detail_data,
                           viewer_role=current_user.role)




@admin_bp.route('/manage-timetables')
@login_required
@admin_required
def manage_timetables():
    try:
        # Fetch data needed for the draggable items and selectors
        teachers = auth_manager.get_all_teachers()
        subjects = student_manager.get_all_subjects() # Assuming this function exists
        # You may need a function to get all grades/sections as well
    except Exception as e:
        current_app.logger.error(f"Error fetching data for timetable management page: {e}")
        flash("Could not load necessary data for the page.", "error")
        teachers, subjects = [], []
        
    return render_template(
        'admin_manage_timetable.html', 
        teachers=teachers, 
        subjects=subjects
    )



# In src/blueprints/admin_bp.py
@admin_bp.route('/grade/<int:grade_id>/sections', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_sections(grade_id):
    """
    Displays existing sections for a grade and allows the admin to add new ones.
    """
    grade = student_manager.get_grade_by_id(grade_id)
    if not grade:
        flash("Grade not found.", "error")
        return redirect(url_for('admin_bp.curriculum_manager_page'))

    form = AddSectionForm()
    if form.validate_on_submit():
        section_name = form.section_name.data
        if student_manager.add_section(grade_id, section_name, form.description.data):
            flash(f"Section '{section_name.upper()}' was created successfully for {grade['grade_name']}.", "success")
        else:
            flash(f"Failed to create section '{section_name.upper()}'. It might already exist.", "danger")
        return redirect(url_for('admin_bp.manage_sections', grade_id=grade_id))

    # Fetch the list of already created sections for this grade
    sections_list = student_manager.get_sections_for_grade(grade_id)
    
    # Get parent info for breadcrumbs/titles
    category = student_manager.get_category_by_id(grade['category_id'])
    subject = student_manager.get_subject_by_id(category['subject_id']) if category else None

    return render_template(
        'admin_manage_sections.html',
        grade=grade,
        category=category,
        subject=subject,
        sections=sections_list, # Pass the list of sections to the template
        form=form
    )



@admin_bp.route('/question-bank')
@login_required
@admin_required # Or @teacher_required if teachers can also access
def question_bank_page():
    """Renders the main user interface for the Question Bank."""
    # This form will be used for the "Add/Edit" modal
    form = AddQuizQuestionForm()

    # Pre-populate the form's dropdowns with all possible choices
    # This data will also be used to populate the filter dropdowns
    try:
        all_subjects = student_manager.get_all_subjects()
        all_categories = student_manager.get_all_categories_for_selection()
        all_grades = student_manager.get_all_grades_for_selection()

        form.subject_id.choices = [(s['subject_id'], s['subject_name']) for s in all_subjects]
        form.subject_id.choices.insert(0, ('', 'All Subjects'))
        
        form.category_id.choices = [(c['category_id'], f"{c['subject_name']} / {c['category_name']}") for c in all_categories]
        form.category_id.choices.insert(0, ('', 'All Categories'))
        
        form.target_grade_id.choices = [(g['grade_id'], f"{g['subject_name']}/{g['category_name']}/{g['grade_name']}") for g in all_grades]
        form.target_grade_id.choices.insert(0, ('', 'All Grades'))

    except Exception as e:
        current_app.logger.error(f"Error populating choices for Question Bank: {e}")
        flash("Could not load filter data.", "error")

    # Initially load all questions. The JavaScript will handle filtering.
    all_questions = student_manager.get_all_quiz_questions_with_options()

    return render_template(
        'admin_question_bank.html',
        form=form,
        questions=all_questions,
        all_subjects=all_subjects,
        all_categories=all_categories,
        all_grades=all_grades
    )





@admin_bp.route('/question-bank/import', methods=['POST'])
@login_required
@admin_required
def question_bank_import():
    """Handles the bulk import of questions from a file."""
    if 'question_file' not in request.files:
        flash('No file part in the request.', 'danger')
        return redirect(url_for('admin_bp.question_bank_page'))
    
    file = request.files['question_file']
    if file.filename == '':
        flash('No file selected.', 'warning')
        return redirect(url_for('admin_bp.question_bank_page'))

    if file:
        try:
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(current_app.root_path, 'temp_uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            result = student_manager.import_questions_from_file(file_path, current_user.id)

            os.remove(file_path)

            flash(result.get('message'), 'success' if result.get('success') else 'danger')
            if result.get('failed_rows'):
                failed_info = "; ".join([f"Row {r}: {e}" for r, e in result['failed_rows']])
                flash(f"Details on failed rows: {failed_info}", 'warning')

        except Exception as e:
            current_app.logger.error(f"Error during file import process: {e}")
            flash(f"An unexpected error occurred during import: {e}", 'danger')

    return redirect(url_for('admin_bp.question_bank_page'))



# Add these two new routes to the end of src/blueprints/admin_bp.py

@admin_bp.route('/upload-users', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_users():
    form = BulkUserUploadForm()
    if form.validate_on_submit():
        file = form.excel_file.data
        filename = secure_filename(file.filename)
        
        # Create a temporary folder to store the upload
        upload_folder = os.path.join(current_app.root_path, 'temp_uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        
        try:
            file.save(file_path)
            
            # Call our backend function from Step 1
            result = auth_manager.bulk_create_users_from_excel(file_path)

            if result.get('error'):
                flash(result['error'], 'danger')
            else:
                success_count = result.get('success_count', 0)
                failed_rows = result.get('failed_rows', [])
                
                flash(f"Successfully created {success_count} users.", 'success')
                
                if failed_rows:
                    # Log and flash details about failed rows
                    failed_details = "; ".join([f"Row {item['row']} ('{item['username']}'): {item['reason']}" for item in failed_rows])
                    current_app.logger.warning(f"Bulk upload failed rows: {failed_details}")
                    flash(f"Skipped {len(failed_rows)} users due to errors. Details: {failed_details}", 'warning')
            
        except Exception as e:
            current_app.logger.error(f"Error processing uploaded file: {e}")
            flash(f"An unexpected error occurred: {e}", "danger")
        finally:
            # Clean up the uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)

        return redirect(url_for('admin_bp.upload_users'))

    return render_template('admin_upload_users.html', form=form)


# In src/blueprints/admin_bp.py
@admin_bp.route('/upload-users/template')
@login_required
@admin_required
def download_user_template():
    data = {
        'username': ['student1', 'teacher1', 'student2'],
        'email': ['student1@example.com', 'teacher1@example.com', 'student2@example.com'],
        'password': ['StudentPass123', 'TeacherPass123', 'StudentPass456'],
        'role': ['student', 'teacher', 'student'],
        'full_name': ['First Student', 'First Teacher', 'Second Student'],
        # New optional columns for student assignment
        'subject_name': ['Islamic Studies', '', 'Islamic Studies'],
        'category_name': ['Quran', '', 'Fiqh'], # <-- ADDED
        'grade_name': ['Grade 1', '', 'Grade 1'],
        'section_name': ['A', '', 'B']
    }
    df = pd.DataFrame(data)
    
    temp_dir = os.path.join(current_app.root_path, 'temp_uploads')
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, 'user_upload_template.xlsx')
    
    df.to_excel(file_path, index=False, engine='openpyxl')
    
    return send_from_directory(directory=temp_dir, path='user_upload_template.xlsx', as_attachment=True)




# Add this new route to the end of src/blueprints/admin_bp.py

# In src/blueprints/admin_bp.py, replace the debug_user_data function

# In src/blueprints/admin_bp.py, replace the debug_user_data function

# In src/blueprints/admin_bp.py, replace the debug_user_data function

# In src/blueprints/admin_bp.py, replace the debug_user_data function

@admin_bp.route('/debug/user-data')
@login_required
@admin_required
def debug_user_data():
    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Get counts
    cursor.execute("SELECT COUNT(*) FROM users;")
    total_users = cursor.fetchone()['COUNT(*)']

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student';")
    student_role_users = cursor.fetchone()['COUNT(*)']

    cursor.execute("SELECT COUNT(*) FROM students;")
    student_profiles = cursor.fetchone()['COUNT(*)']

    # --- FIX: Query only columns that exist in the 'users' table ---
    cursor.execute("SELECT user_id, username, role, created_at FROM users ORDER BY user_id;")
    all_users_data = cursor.fetchall()

    # Query the students table separately
    cursor.execute("SELECT student_id, user_id, name, contact_info, created_at FROM students ORDER BY student_id;")
    all_students_data = cursor.fetchall()

    conn.close()

    return render_template('debug_user_data_report.html',
                           total_users=total_users,
                           student_role_users=student_role_users,
                           student_profiles=student_profiles,
                           all_users_data=all_users_data,
                           all_students_data=all_students_data)



@admin_bp.route('/subject/<int:subject_id>/rubrics', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_rubrics(subject_id):
    """
    Main page for viewing and adding rubrics for a specific subject.
    """
    subject = student_manager.get_subject_by_id(subject_id)
    if not subject:
        flash("Subject not found.", "error")
        return redirect(url_for('admin_bp.curriculum_manager_page'))

    form = RubricForm()
    
    # Handle the form submission for ADDING a new rubric
    if form.validate_on_submit():
        new_rubric_id = curriculum_manager.add_rubric(
            subject_id=subject_id,
            title=form.title.data,
            description=form.description.data,
            level_1=form.level_1_desc.data,
            level_2=form.level_2_desc.data,
            level_3=form.level_3_desc.data,
            level_4=form.level_4_desc.data
        )
        if new_rubric_id:
            flash(f"Rubric '{form.title.data}' added successfully!", "success")
        else:
            flash("Failed to add rubric. The title might already exist for this subject.", "danger")
        return redirect(url_for('admin_bp.manage_rubrics', subject_id=subject_id))

    rubrics = curriculum_manager.get_rubrics_for_subject(subject_id)
    
    return render_template('admin_manage_rubrics.html', 
                           subject=subject, 
                           rubrics=rubrics, 
                           form=form)

@admin_bp.route('/rubric/<int:rubric_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_rubric(rubric_id):
    """
    Handles the form submission for EDITING an existing rubric.
    This route is called via JavaScript from the modal form.
    """
    rubric = curriculum_manager.get_rubric_by_id(rubric_id)
    if not rubric:
        flash("Rubric not found.", "error")
        return redirect(request.referrer or url_for('admin_bp.curriculum_manager_page'))

    form = RubricForm()
    if form.validate_on_submit():
        success = curriculum_manager.update_rubric(
            rubric_id=rubric_id,
            title=form.title.data,
            description=form.description.data,
            level_1=form.level_1_desc.data,
            level_2=form.level_2_desc.data,
            level_3=form.level_3_desc.data,
            level_4=form.level_4_desc.data
        )
        if success:
            flash(f"Rubric '{form.title.data}' updated successfully!", "success")
        else:
            flash("Failed to update rubric.", "danger")
    else:
        flash("Failed to validate the form for editing.", "warning")
        
    return redirect(url_for('admin_bp.manage_rubrics', subject_id=rubric['subject_id']))

@admin_bp.route('/rubric/<int:rubric_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_rubric(rubric_id):
    """
    Handles the deletion of a rubric.
    """
    rubric = curriculum_manager.get_rubric_by_id(rubric_id)
    if rubric and curriculum_manager.delete_rubric(rubric_id):
        flash(f"Rubric '{rubric['title']}' deleted successfully.", "success")
        return redirect(url_for('admin_bp.manage_rubrics', subject_id=rubric['subject_id']))
    else:
        flash("Failed to delete rubric.", "danger")
        return redirect(request.referrer or url_for('admin_bp.curriculum_manager_page'))
    



# Add this new route to the end of src/blueprints/admin_bp.py
@admin_bp.route('/debug/sections-data')
@login_required
@admin_required
def debug_sections_data():
    """
    Displays the raw content of the sections table for debugging.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.section_id, s.section_name, s.description, s.grade_id, g.grade_name
        FROM sections s
        JOIN grades g ON s.grade_id = g.grade_id
        ORDER BY s.grade_id, s.section_name;
    """)
    sections = cursor.fetchall()
    conn.close()
    return render_template('sections_report.html', sections=sections)