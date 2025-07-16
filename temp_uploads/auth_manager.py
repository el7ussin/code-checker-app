 # src/auth_manager.py
import sqlite3
import sys
from typing import Optional, List, Dict, Any, Set
from src import bcrypt, db # <<< ADD , db HERE
from flask_bcrypt import Bcrypt
from .database import get_db_connection, DB_FILE # Import from the new file
from .models import User, Student, Subject, Category, Grade, Section # <--- ADD THIS LINE
import datetime
from collections import defaultdict # Ensure imported
from flask import flash, url_for, current_app
from . import student_manager
from sqlalchemy import func
import pandas as pd
from werkzeug.security import generate_password_hash
from .database import get_db_connection
import traceback




# Initialize Bcrypt (needs Flask app instance, ensure initialized in app.py: bcrypt.init_app(app))

def create_user(username, password, role='teacher', full_name: Optional[str] = None, email: Optional[str] = None) -> Optional[int]:
    """
    Creates a new user AND their basic profile.
    Returns the new user_id on success, None on failure.
    """
    new_user_id = None
    conn = None

    if role not in ['admin', 'teacher', 'student', 'coordinator', 'supervisor']: # Modified role check
        print(f"Error: Invalid role specified ('{role}').")
        return None

    try:
        with get_db_connection() as check_conn:
            cursor = check_conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                print(f"Error: Username '{username}' already exists.")
                return None
    except sqlite3.Error as e:
         print(f"Database error checking username existence: {e}")
         return None

    try:
        conn = get_db_connection()
        conn.execute("BEGIN")
        cursor = conn.cursor()

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        user_sql = "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)"
        cursor.execute(user_sql, (username, password_hash, role))
        new_user_id = cursor.lastrowid
        if not new_user_id:
            raise sqlite3.Error("Failed to get last row ID for new user.")

        profile_sql = "INSERT INTO user_profiles (user_id, full_name, email) VALUES (?, ?, ?)"
        email_to_insert = email.strip() if isinstance(email, str) and email.strip() else None
        cursor.execute(profile_sql, (new_user_id, full_name, email_to_insert))

        conn.commit()
        print(f"User '{username}' and profile created successfully with User ID {new_user_id}.")
        return new_user_id

    except sqlite3.IntegrityError as ie:
        if conn: conn.rollback()
        if 'users.username' in str(ie) or 'idx_username' in str(ie): print(f"Error: Username '{username}' already exists (Integrity Error).")
        elif 'user_profiles.email' in str(ie) or 'idx_profile_email' in str(ie): print(f"Error: Email '{email if email else 'provided'}' already exists.")
        elif 'users.role' in str(ie): print(f"Database Integrity Error: Role ('{role}') failed CHECK constraint.")
        else: print(f"Database Integrity Error creating user/profile '{username}': {ie}")
        return None
    except sqlite3.Error as e:
        if conn: conn.rollback()
        print(f"Database error during user/profile creation: {e}")
        return None
    except Exception as e:
        if conn: conn.rollback()
        print(f"Unexpected error for {username}: {e}")
        return None
    finally:
         if conn:
             try: conn.close()
             except Exception as e_close: print(f"Error closing connection for {username}: {e_close}")


def get_user_by_username(username: str) -> Optional[User]:
    """Retrieves a user object by username."""
    user_data = None
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
            cursor = conn.cursor()
            # Ensure you select all fields needed by the User model (user_id, username, role)
            cursor.execute("SELECT user_id, username, role, password_hash FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                # Pass password_hash if your User model needs it, otherwise omit
                user_data = User(user_id=row['user_id'], username=row['username'], role=row['role']) # Removed password_hash if not needed by User model for login manager
                # Or if User model stores the hash:
                # user_data = User(user_id=row['user_id'], username=row['username'], role=row['role'], password_hash=row['password_hash'])
    except sqlite3.Error as e:
        print(f"Database error fetching user by username: {e}")
    return user_data


def get_user_by_id(user_id: int) -> Optional[User]:
    """Retrieves a user object by ID using the ORM (needed for Flask-Login)."""
    try:
        # This is the standard way to get a user by ID with Flask-SQLAlchemy
        return User.query.get(int(user_id))
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error fetching user by ID {user_id}: {e}")
    return None


def get_user_details(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves full user and profile details as dict by ID."""
    sql = """
        SELECT u.user_id, u.username, u.role, u.created_at,
               p.profile_id, p.full_name, p.email, p.phone, p.bio, p.last_updated
        FROM users u
        LEFT JOIN user_profiles p ON u.user_id = p.user_id
        WHERE u.user_id = ?
    """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Database error fetching user details for ID {user_id}: {e}")
        return None


def update_user_profile(user_id: int, full_name: Optional[str], email: Optional[str], phone: Optional[str], bio: Optional[str]) -> bool:
    """Updates or creates a user's profile."""
    email_to_set = email.strip() if isinstance(email, str) and email.strip() else None
    sql = """
        INSERT INTO user_profiles (user_id, full_name, email, phone, bio, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name = excluded.full_name,
            email = excluded.email,
            phone = excluded.phone,
            bio = excluded.bio,
            last_updated = excluded.last_updated;
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.datetime.now().isoformat()
            cursor.execute(sql, (user_id, full_name, email_to_set, phone, bio, now))
            conn.commit()
            return True
    except sqlite3.IntegrityError as ie:
        print(f"Database Integrity Error updating profile for user {user_id}. Email unique? Error: {ie}")
        return False
    except sqlite3.Error as e:
        print(f"Database error updating profile for user {user_id}: {e}")
        return False



def verify_user(username, password) -> Optional[User]:
    """
    Verifies username and password using the ORM. 
    Returns User object on success, None otherwise.
    """
    try:
        # Find the user by their username using the new model
        user = User.query.filter_by(username=username).first()

        # If the user exists and the password hash matches, return the user object
        if user and bcrypt.check_password_hash(user.password_hash, password):
            return user
    except Exception as e:
        # Use current_app logger which is safer in modules
        from flask import current_app
        current_app.logger.error(f"Error during user verification for {username}: {e}")
    
    # If user is not found or password doesn't match, return None
    return None


def get_all_users() -> List[Dict[str, Any]]:
    """Retrieves all users with basic profile info from the database."""
    users = []
    sql = """
        SELECT u.user_id, u.username, u.role, u.created_at,
               p.full_name, p.email
        FROM users u
        LEFT JOIN user_profiles p ON u.user_id = p.user_id
        ORDER BY u.role, u.username
    """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            users = [dict(row) for row in rows]
            # Format dates
            for user in users:
                created_at_str = user.get('created_at')
                try:
                    if created_at_str:
                        dt_obj = datetime.datetime.fromisoformat(created_at_str)
                        user['created_at_formatted'] = dt_obj.strftime('%Y-%m-%d') # Changed format
                    else: user['created_at_formatted'] = "N/A"
                except (ValueError, TypeError): # Catch specific errors
                    user['created_at_formatted'] = created_at_str # Fallback
                # --- FIXED: Removed duplicated/incomplete line below ---
    except sqlite3.Error as e:
        print(f"Error fetching all users: {e}")
    return users


def get_user_counts_by_role() -> Dict[str, int]:
    """Gets the count of users for each role using the ORM."""
    # Define the roles you want to count
    roles_to_count = ['admin', 'teacher', 'student', 'coordinator', 'supervisor']
    counts = {role: 0 for role in roles_to_count}
    total = 0
    
    try:
        # This query groups users by their role and counts them
        role_counts_query = db.session.query(
            User.role, 
            func.count(User.id)
        ).group_by(User.role).all()

        # The result will be like: [('admin', 5), ('teacher', 20), ...]
        for role, count in role_counts_query:
            if role in counts:
                counts[role] = count
            total += count
        
        counts['total'] = total

    except Exception as e:
        current_app.logger.error(f"Error getting user counts by role: {e}")
        # Return a dictionary with error values if something goes wrong
        return {role: "Err" for role in roles_to_count} | {"total": "Err"}
        
    return counts



def get_all_teachers() -> List[Dict[str, Any]]:
    """Retrieves a list of all users with the 'teacher' role."""
    teachers = []
    # Assuming 'users' table has 'user_id', 'username' and 'role' columns
    # Optionally join with user_profiles if full_name is needed here
    sql = """
        SELECT u.user_id, u.username, p.full_name
        FROM users u
        LEFT JOIN user_profiles p ON u.user_id = p.user_id
        WHERE u.role = 'teacher'
        ORDER BY u.username;
        """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            teachers = [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"Database error fetching all teachers: {e}")
    return teachers



def get_assigned_grade_count_for_teacher(teacher_user_id: int) -> int:
    """Counts the number of unique grades a teacher is assigned to (via any section letter)."""
    count = 0
    # --- UPDATED SQL Query ---
    # Counts distinct grade_ids from the NEW assignment table
    # Adjust table/column names if needed
    sql = """
        SELECT COUNT(DISTINCT tgsa.grade_id)
        FROM teacher_grade_section_assignments tgsa -- <<< Use NEW table name
        WHERE tgsa.teacher_user_id = ?;
    """
    # --- End Adjust ---
    try:
        with get_db_connection() as conn: # Ensure get_db_connection is accessible
            cursor = conn.cursor()
            cursor.execute(sql, (teacher_user_id,))
            result = cursor.fetchone()
            if result:
                count = result[0]
    except sqlite3.Error as e:
        print(f"Database error counting assigned grades for teacher {teacher_user_id}: {e}")
    except Exception as e:
        print(f"Unexpected error counting assigned grades for teacher {teacher_user_id}: {e}")
    return count

# Add this function to auth_manager.py (or relevant manager)

def is_quiz_created_by_teacher(quiz_id: int, teacher_user_id: int) -> bool:
    """Checks if a specific quiz was created by a specific teacher."""
    is_owner = False
    # --- Adjust table/column names ---
    sql = "SELECT 1 FROM quizzes WHERE quiz_id = ? AND created_by_user_id = ? LIMIT 1;"
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (quiz_id, teacher_user_id))
            if cursor.fetchone():
                is_owner = True
    except sqlite3.Error as e:
        print(f"DB error checking quiz ownership Q:{quiz_id} T:{teacher_user_id}: {e}")

    print(f"DEBUG [is_quiz_created_by_teacher]: Q:{quiz_id}, T:{teacher_user_id}, Owner:{is_owner}")
    return is_owner
# --- End Function ---


# Add this function to src/auth_manager.py
def update_user(user_id: int, username: str, full_name: Optional[str], email: Optional[str], new_password: Optional[str] = None, role: Optional[str] = None) -> bool:
    """
    Updates user information in users and user_profiles table.
    Optionally updates password if new_password is provided.
    Checks for username/email uniqueness (excluding the user being updated).

    Args:
        user_id: The ID of the user to update.
        username: The new username.
        full_name: The new full name (for user_profiles).
        email: The new email (for user_profiles).
        new_password: The new plaintext password (if changing), otherwise None.
        role: The new role (if changing), otherwise None.

    Returns:
        True on success, False on failure (e.g., DB error, uniqueness violation).
    """
    if not username or not username.strip():
        print("Error: Username cannot be empty.")
        return False

    # --- Check for uniqueness conflicts (excluding self) ---
    check_sql = "SELECT user_id FROM users WHERE username = ? AND user_id != ?"
    check_email_sql = "SELECT user_id FROM user_profiles WHERE email = ? AND user_id != ? AND email IS NOT NULL AND email != ''"
    # --- End Check ---

    # --- Build UPDATE statements ---
    user_update_fields = ["username = ?"]
    user_params = [username.strip()]
    if role: # Only include role if it's being changed
         user_update_fields.append("role = ?")
         user_params.append(role)

    profile_update_fields = []
    profile_params = []
    if full_name is not None: profile_update_fields.append("full_name = ?"); profile_params.append(full_name.strip())
    if email is not None: profile_update_fields.append("email = ?"); profile_params.append(email.strip() or None) # Store empty email as NULL

    # Hash password ONLY if a new one is provided
    if new_password and new_password.strip():
        if not bcrypt: # Ensure bcrypt object is available
             print("ERROR: Bcrypt object not configured in auth_manager.")
             return False
        try:
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            user_update_fields.append("password_hash = ?")
            user_params.append(hashed_password)
        except Exception as e:
            print(f"Error hashing new password: {e}")
            return False

    # Add user_id for WHERE clause
    user_params.append(user_id)
    profile_params.append(user_id)

    user_sql = f"UPDATE users SET {', '.join(user_update_fields)} WHERE user_id = ?;"
    profile_sql = f"UPDATE user_profiles SET {', '.join(profile_update_fields)} WHERE user_id = ?;" if profile_update_fields else None

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN")

        # Check username uniqueness
        cursor.execute(check_sql, (username.strip(), user_id))
        if cursor.fetchone():
            print(f"Error: Username '{username.strip()}' already taken.")
            flash(f"Username '{username.strip()}' is already taken.", "error") # Flash from helper
            conn.rollback()
            return False

        # Check email uniqueness if email is provided and not empty
        if email and email.strip():
             cursor.execute(check_email_sql, (email.strip(), user_id))
             if cursor.fetchone():
                  print(f"Error: Email '{email.strip()}' already taken.")
                  flash(f"Email '{email.strip()}' is already taken.", "error") # Flash from helper
                  conn.rollback()
                  return False

        # Update users table
        print(f"DEBUG: Updating users table: {user_sql} with {user_params}")
        cursor.execute(user_sql, user_params)
        users_updated = cursor.rowcount

        # Update user_profiles table (if fields were provided)
        profiles_updated = 0
        if profile_sql:
             print(f"DEBUG: Updating user_profiles table: {profile_sql} with {profile_params}")
             cursor.execute(profile_sql, profile_params)
             profiles_updated = cursor.rowcount

        conn.commit()
        print(f"User {user_id} updated. users rows: {users_updated}, user_profiles rows: {profiles_updated}")
        # Return True if at least the users table was found and potentially updated
        return users_updated > 0 or profiles_updated > 0

    except sqlite3.Error as e:
        if conn: conn.rollback()
        print(f"Database error updating user {user_id}: {e}")
        flash("Database error updating user.", "error")
        return False
    except Exception as e:
         if conn: conn.rollback()
         print(f"Unexpected error updating user {user_id}: {e}")
         flash("An unexpected error occurred.", "error")
         return False
    finally:
         if conn: conn.close()
# --- End update_user ---

def delete_user(user_id):
    """
    Deletes a user from the users table. Relies on the database schema's
    ON DELETE CASCADE and ON DELETE SET NULL to handle related data.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # With the corrected schema, this is the only command needed.
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        # Return True if a row was actually deleted
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        # Log the error for debugging
        try:
            from flask import current_app
            current_app.logger.error(f"Database error during user deletion for user_id {user_id}: {e}")
            traceback.print_exc()
        except (ImportError, RuntimeError):
            print(f"ERROR: Could not delete user {user_id}. Reason: {e}")
        return False
    finally:
        conn.close()


# --- End Function ---


# Add this function to src/auth_manager.py
def get_teachers_for_grade_section(grade_id, section_letter):
    """
    Fetches all teachers assigned to a specific grade and section.
    This version uses a robust query to avoid common data mismatch issues.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # This query uses UPPER and TRIM to make the section name comparison case-insensitive
    # and immune to leading/trailing whitespace, which is a common source of errors.
    query = """
        SELECT u.user_id, u.username AS full_name
        FROM users u
        JOIN teacher_grade_section_assignments tgsa ON u.user_id = tgsa.teacher_user_id
        JOIN sections s ON tgsa.section_id = s.section_id
        WHERE tgsa.grade_id = ? AND UPPER(TRIM(s.section_name)) = UPPER(TRIM(?))
        AND u.role = 'teacher'
        GROUP BY u.user_id, u.username
        ORDER BY u.username;
    """
    try:
        # Pass the original section_letter to the query
        cursor.execute(query, (grade_id, section_letter))
        teachers = cursor.fetchall()
        # The template expects 'full_name', so we provide it from username
        return [dict(row) for row in teachers] if teachers else []
    except Exception as e:
        print(f"DB error fetching teachers for G:{grade_id} S:{section_letter}: {e}")
        return []
    finally:
        conn.close()

# --- End Function ---


# Add this function to src/auth_manager.py
def update_avatar(user_id: int, new_avatar_filename: Optional[str]) -> bool:
    """
    Updates the avatar filename for a given user_id in the user_profiles table.
    Accepts None or an empty string to clear the avatar (revert to default).
    """
    # Basic validation/cleaning
    if new_avatar_filename is not None:
        new_avatar_filename = new_avatar_filename.strip()
        # Optional extra validation: Check if filename is plausible (e.g., ends in .png)?
        # Or check if it actually exists in the static folder? (Might be better done in route/JS)
        if not new_avatar_filename: # Treat empty string like None
            new_avatar_filename = None

    # --- Adjust table/column names ---
    sql = "UPDATE user_profiles SET avatar_filename = ? WHERE user_id = ?;"
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Use None if filename is empty/None, otherwise use the filename string
            cursor.execute(sql, (new_avatar_filename, user_id))
            conn.commit()
            if cursor.rowcount > 0:
                print(f"DEBUG: Avatar updated for user {user_id} to '{new_avatar_filename}'")
                return True
            else:
                # This might happen if the user_id doesn't have a profile row yet
                print(f"Warning: No user_profile found for user_id {user_id} to update avatar.")
                # Should we create a profile row here? Or assume it exists? Assume it exists for now.
                return False # Indicate update didn't happen
    except sqlite3.Error as e:
        print(f"Database error updating avatar for user {user_id}: {e}")
        return False
    except Exception as e:
         print(f"Unexpected error updating avatar for user {user_id}: {e}")
         return False


def create_notification(user_id: int, message: str, link_url: Optional[str] = None) -> bool:
    """
    Creates a new notification for a specific user.

    Args:
        user_id: The ID of the user the notification is for.
        message: The text content of the notification.
        link_url: (Optional) A URL string for the notification link.

    Returns:
        True if the notification was created successfully, False otherwise.
    """
    if not user_id or not message or not message.strip():
        print("Error: user_id and message are required to create a notification.")
        return False

    sql = """
        INSERT INTO notifications (user_id, message, link_url, is_read)
        VALUES (?, ?, ?, 0); -- is_read defaults to 0 (unread)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id, message.strip(), link_url))
            conn.commit()
            print(f"DEBUG: Notification created for user {user_id}")
            return True
    except sqlite3.Error as e:
        # Could fail if user_id doesn't exist due to FOREIGN KEY constraint
        print(f"Database error creating notification for user {user_id}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error creating notification for user {user_id}: {e}")
        return False

def get_notifications_for_user(user_id: int, limit: int = 10, only_unread: bool = False) -> List[Dict[str, Any]]:
    """
    Retrieves notifications for a specific user, ordered by most recent first.

    Args:
        user_id: The ID of the user whose notifications to fetch.
        limit: The maximum number of notifications to return.
        only_unread: If True, only fetches notifications where is_read = 0.

    Returns:
        A list of notification dictionaries.
    """
    notifications = []
    # Note: Adjust column names if your schema differs slightly
    sql = """
        SELECT notification_id, user_id, message, link_url, is_read, created_at
        FROM notifications
        WHERE user_id = ?
    """
    params: List[Any] = [user_id]

    if only_unread:
        sql += " AND is_read = 0"
        # No parameter needed for 'is_read = 0'

    sql += " ORDER BY created_at DESC LIMIT ?;"
    params.append(limit)

    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row # Ensure rows are dict-like
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            notifications = [dict(row) for row in rows]
            # Optional: Format 'created_at' here if desired for display
            for notif in notifications:
                created_at_str = notif.get('created_at')
                try:
                    notif['created_at_formatted'] = datetime.datetime.fromisoformat(created_at_str).strftime('%Y-%m-%d %H:%M') if created_at_str else 'N/A'
                except:
                    notif['created_at_formatted'] = created_at_str # Fallback
    except sqlite3.Error as e:
        print(f"Database error fetching notifications for user {user_id}: {e}")
    except Exception as e:
        print(f"Unexpected error fetching notifications for user {user_id}: {e}")

    return notifications

def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    """
    Marks a specific notification as read, ensuring it belongs to the user.

    Args:
        notification_id: The ID of the notification to mark as read.
        user_id: The ID of the user attempting to mark it read (for verification).

    Returns:
        True if the notification was successfully marked read, False otherwise.
    """
    sql = """
        UPDATE notifications
        SET is_read = 1
        WHERE notification_id = ? AND user_id = ? AND is_read = 0;
    """ # Only update if it exists, belongs to user, and is currently unread
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (notification_id, user_id))
            conn.commit()
            # Check if any row was actually updated
            if cursor.rowcount > 0:
                print(f"DEBUG: Marked notification {notification_id} as read for user {user_id}")
                return True
            else:
                # This means notification didn't exist, didn't belong to user, or was already read
                print(f"DEBUG: Notification {notification_id} not updated (not found, wrong user, or already read)")
                return False
    except sqlite3.Error as e:
        print(f"Database error marking notification {notification_id} read for user {user_id}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error marking notification {notification_id} read: {e}")
        return False

# --- Optional Helper Functions ---

def mark_all_notifications_as_read(user_id: int) -> bool:
     """Marks all unread notifications for a user as read."""
     sql = "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0;"
     try:
         with get_db_connection() as conn:
             cursor = conn.cursor()
             cursor.execute(sql, (user_id,))
             conn.commit()
             print(f"DEBUG: Marked all as read for user {user_id}. Rows affected: {cursor.rowcount}")
             return True
     except sqlite3.Error as e:
         print(f"DB error marking all notifications read for user {user_id}: {e}")
         return False

def count_unread_notifications(user_id: int) -> int:
     """Counts unread notifications for a user."""
     count = 0 # Initialize to 0 (default value)
     sql = "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0;"
     try:
         with get_db_connection() as conn: # Ensure get_db_connection is imported from .database
             cursor = conn.cursor()
             cursor.execute(sql, (user_id,))
             result = cursor.fetchone()
             if result and result[0] is not None:
                 count = result[0]
     except sqlite3.Error as e:
         print(f"DB error counting unread notifications for user {user_id}: {e}")
         # Keep count = 0 if there's a DB error
     except Exception as e:
         print(f"Unexpected error counting unread notifications for user {user_id}: {e}")
         # Keep count = 0 on other errors too

     # --- ENSURE THIS LINE IS PRESENT AND CORRECTLY INDENTED ---
     return count # Always return the integer count
     # --- END ENSURE -


# In src/auth_manager.py, replace this entire function.

def get_assigned_sections_for_teacher(teacher_user_id: int) -> list:
    """
    Fetches a detailed list of all sections assigned to a teacher,
    including category, subject, and an accurate student count for each section.
    FIX: This query is now based on the correct database schema.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT
            g.grade_id,
            g.grade_name,
            tgsa.section_letter,
            cat.category_id,
            cat.category_name,
            sub.subject_id,
            sub.subject_name,
            (SELECT COUNT(student_id)
             FROM student_grade_section_assignments sgsa
             WHERE sgsa.grade_id = g.grade_id AND sgsa.section_letter = tgsa.section_letter) as student_count
        FROM teacher_grade_section_assignments tgsa
        JOIN grades g ON tgsa.grade_id = g.grade_id
        JOIN categories cat ON g.category_id = cat.category_id
        JOIN subjects sub ON cat.subject_id = sub.subject_id
        WHERE tgsa.teacher_user_id = ?
        ORDER BY sub.subject_name, cat.category_name, g.grade_name, tgsa.section_letter;
    """
    try:
        cursor.execute(query, (teacher_user_id,))
        assignments = cursor.fetchall()
        return [dict(row) for row in assignments] if assignments else []
    except Exception as e:
        print(f"DB error fetching assigned sections for teacher {teacher_user_id}: {e}")
        return []
    finally:
        conn.close()

# --- End Function ---




def get_notification_by_id(notification_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single notification by its ID, ensuring it belongs to the user."""
    notification = None
    # Select all relevant columns
    sql = """
        SELECT notification_id, user_id, message, link_url, is_read, created_at
        FROM notifications
        WHERE notification_id = ? AND user_id = ?;
    """
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (notification_id, user_id))
            row = cursor.fetchone()
            if row:
                notification = dict(row)
                # Optional: Format date? Not strictly needed here.
    except sqlite3.Error as e:
        print(f"DB error fetching notification {notification_id} for user {user_id}: {e}")
    except Exception as e:
        print(f"Unexpected error fetching notification {notification_id} for user {user_id}: {e}")

    return notification



def get_assigned_teacher_ids_for_student(student_id: int) -> List[int]:
    sql = """
        SELECT teacher_id
        FROM teacher_student_assignments
        WHERE student_id = ?
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (student_id,))
            rows = cursor.fetchall()
            return [row['teacher_id'] for row in rows]
    except Exception as e:
        print(f"Error fetching assigned teachers for student {student_id}: {e}")
        return []




# In src/auth_manager.py, replace this function

def assign_teacher_to_student(teacher_user_id, student_id, admin_user_id):
    """
    Assigns a specific teacher to a specific student.
    FIX: Corrected to match the actual table schema.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # The 'assigned_by_user_id' column was incorrect and has been removed.
        cursor.execute(
            "INSERT INTO student_teacher_assignments (teacher_id, student_id) VALUES (?, ?)",
            (teacher_user_id, student_id)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # This can happen if the assignment already exists
        return False
    except Exception as e:
        print(f"DB error assigning Teacher:{teacher_user_id} to Student:{student_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def unassign_teacher_from_student(teacher_user_id: int, student_id: int) -> bool:
    """Unassigns a specific teacher directly from a specific student."""
    # --- Corrected Table Name ---
    sql = "DELETE FROM student_teacher_assignments WHERE teacher_user_id = ? AND student_id = ?;"
    # --- End Correction ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (teacher_user_id, student_id))
            conn.commit()
            print(f"DEBUG: Unassigned Teacher:{teacher_user_id} from Student:{student_id} (Rows: {cursor.rowcount})")
            return True # Return True even if row didn't exist
    except sqlite3.Error as e:
        print(f"DB error unassigning Teacher:{teacher_user_id} from Student:{student_id}: {e}")
        return False

def get_teachers_for_student(student_id: int) -> List[Dict[str, Any]]:
    """Retrieves details of teachers directly assigned to a specific student."""
    teachers = []
    # --- Corrected Table Name ---
    sql = """
        SELECT u.user_id, u.username, p.full_name
        FROM users u
        JOIN student_teacher_assignments sta ON u.user_id = sta.teacher_user_id
        LEFT JOIN user_profiles p ON u.user_id = p.user_id
        WHERE sta.student_id = ? AND u.role = 'teacher'
        ORDER BY p.full_name, u.username;
    """
    # --- End Correction ---
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (student_id,))
            rows = cursor.fetchall()
            teachers = [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"DB error fetching teachers for student {student_id}: {e}")
        # Return empty list on error
        return []
    except Exception as e:
        print(f"Unexpected error fetching teachers for student {student_id}: {e}")
        return []
    return teachers

def get_assigned_teacher_ids_for_student(student_id: int) -> Set[int]:
    """Retrieves a set of teacher user IDs directly assigned to a specific student."""
    teacher_ids = set()
    # --- Corrected Table Name ---
    sql = "SELECT teacher_user_id FROM student_teacher_assignments WHERE student_id = ?;"
    # --- End Correction ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (student_id,))
            rows = cursor.fetchall()
            teacher_ids = {row[0] for row in rows if row[0] is not None}
    except sqlite3.Error as e:
        # CRITICAL: If this errors (e.g., table missing), return empty SET
        print(f"Error fetching assigned teachers for student {student_id}: {e}")
        return set() # Return empty set on error
    except Exception as e:
        print(f"Unexpected error fetching assigned teachers for student {student_id}: {e}")
        return set() # Return empty set on error
    # Optional debug print
    # print(f"DEBUG [get_assigned_teacher_ids_for_student]: S:{student_id} Assigned T_IDs:{teacher_ids}")
    return teacher_ids # Ensure it returns the set

def unassign_teacher_from_student(teacher_user_id: int, student_id: int) -> bool:
    """Unassigns a specific teacher directly from a specific student."""
    # --- Corrected Table Name ---
    sql = "DELETE FROM student_teacher_assignments WHERE teacher_user_id = ? AND student_id = ?;"
    # --- End Correction ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (teacher_user_id, student_id))
            conn.commit()
            print(f"DEBUG: Unassigned Teacher:{teacher_user_id} from Student:{student_id} (Rows: {cursor.rowcount})")
            return True
    except sqlite3.Error as e:
        print(f"DB error unassigning Teacher:{teacher_user_id} from Student:{student_id}: {e}")
        return False

def get_teachers_for_student(student_id: int) -> List[Dict[str, Any]]:
    """Retrieves details of teachers directly assigned to a specific student."""
    teachers = []
    # --- Corrected Table Name ---
    sql = """
        SELECT u.user_id, u.username, p.full_name
        FROM users u
        JOIN student_teacher_assignments sta ON u.user_id = sta.teacher_user_id
        LEFT JOIN user_profiles p ON u.user_id = p.user_id
        WHERE sta.student_id = ? AND u.role = 'teacher'
        ORDER BY p.full_name, u.username;
    """
    # --- End Correction ---
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (student_id,))
            rows = cursor.fetchall()
            teachers = [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"DB error fetching teachers for student {student_id}: {e}")
    return teachers

def get_assigned_teacher_ids_for_student(student_id: int) -> Set[int]:
    """Retrieves a set of teacher user IDs directly assigned to a specific student."""
    teacher_ids = set()
    # --- Corrected Table Name ---
    sql = "SELECT teacher_user_id FROM student_teacher_assignments WHERE student_id = ?;"
    # --- End Correction ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (student_id,))
            rows = cursor.fetchall()
            teacher_ids = {row[0] for row in rows if row[0] is not None}
    except sqlite3.Error as e:
        # CRITICAL: If this errors (e.g., table missing), return empty SET, not list/None
        print(f"Error fetching assigned teachers for student {student_id}: {e}")
        return set() # Return empty set on error
    # Optional debug print
    # print(f"DEBUG [get_assigned_teacher_ids_for_student]: S:{student_id} Assigned T_IDs:{teacher_ids}")
    return teacher_ids # Ensure it returns the set


# In src/auth_manager.py, please replace all four of the following functions.
# This ensures all teacher assignment logic is consistent.

def assign_teacher_to_grade_section(teacher_user_id, grade_id, section_letter):
    """
    Assigns a teacher to a specific section letter within a grade.
    FIX: This version inserts the section_letter directly, as the table does not have a section_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "INSERT INTO teacher_grade_section_assignments (teacher_user_id, grade_id, section_letter) VALUES (?, ?, ?);"
    try:
        cursor.execute(sql, (teacher_user_id, grade_id, section_letter.upper()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Assignment likely already exists
    except Exception as e:
        print(f"DB error assigning T:{teacher_user_id} to G:{grade_id} S:{section_letter}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def unassign_teacher_from_grade_section(teacher_user_id, grade_id, section_letter):
    """
    Unassigns a teacher from a specific section letter within a grade.
    FIX: This version deletes using the section_letter directly.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "DELETE FROM teacher_grade_section_assignments WHERE teacher_user_id = ? AND grade_id = ? AND section_letter = ?;"
    try:
        cursor.execute(sql, (teacher_user_id, grade_id, section_letter.upper()))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error unassigning teacher: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_assigned_grade_sections_for_teacher(teacher_user_id):
    """
    Fetches all (grade_id, section_letter) tuples for a teacher's assignments.
    FIX: This version selects directly from the assignment table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "SELECT grade_id, section_letter FROM teacher_grade_section_assignments WHERE teacher_user_id = ?;"
    try:
        cursor.execute(sql, (teacher_user_id,))
        assignments = cursor.fetchall()
        return {(row['grade_id'], row['section_letter']) for row in assignments} if assignments else set()
    except Exception as e:
        print(f"DB error fetching assigned grade/sections for teacher {teacher_user_id}: {e}")
        return set()
    finally:
        conn.close()

def get_assigned_grade_section_summary_for_teacher(teacher_user_id):
    """
    Returns a comma-separated string summarizing a teacher's assignments.
    FIX: This version joins with grades but gets the section_letter from the assignment table itself.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT g.grade_name || ' - ' || tgsa.section_letter AS summary
        FROM teacher_grade_section_assignments tgsa
        JOIN grades g ON tgsa.grade_id = g.grade_id
        WHERE tgsa.teacher_user_id = ?
        ORDER BY g.grade_name, tgsa.section_letter;
    """
    try:
        cursor.execute(query, (teacher_user_id,))
        rows = cursor.fetchall()
        return ", ".join([row['summary'] for row in rows]) if rows else "None"
    except Exception as e:
        print(f"DB error fetching assignment summary for teacher {teacher_user_id}: {e}")
        return "Error"
    finally:
        conn.close()


# Add these functions to src/auth_manager.py
# Make sure to import necessary modules:
# sqlite3, Optional, List, Dict, Any, datetime
# from .database import get_db_connection
# from .student_manager import get_student_current_assignment_details # Needed for filtering

# --- Announcement Management Functions ---

def create_announcement(creator_user_id: int, title: str, content: str,
                        audience_role: str = 'all', target_grade_id: Optional[int] = None,
                        target_section_letter: Optional[str] = None, is_active: bool = True) -> Optional[int]:
    """Creates a new announcement."""
    if not title or not title.strip() or not content or not content.strip():
        print("Error: Announcement title and content cannot be empty.")
        return None
    # Validate audience_role
    if audience_role not in ['all', 'student', 'teacher', 'admin']:
        print(f"Warning: Invalid audience_role '{audience_role}'. Defaulting to 'all'.")
        audience_role = 'all'
    # Validate section letter if provided
    if target_section_letter and (len(target_section_letter) != 1 or not 'A' <= target_section_letter.upper() <= 'Z'):
         print(f"Warning: Invalid target_section_letter '{target_section_letter}'. Storing as NULL.")
         target_section_letter = None
    elif target_section_letter:
         target_section_letter = target_section_letter.upper()

    # Convert boolean is_active to integer
    active_int = 1 if is_active else 0

    # --- Adjust SQL ---
    sql = """
        INSERT INTO announcements (creator_user_id, title, content, audience_role,
                                  target_grade_id, target_section_letter, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (creator_user_id, title.strip(), content.strip(), audience_role,
                                 target_grade_id, target_section_letter, active_int))
            conn.commit()
            new_id = cursor.lastrowid
            print(f"Announcement '{title}' created with ID: {new_id}")
            return new_id
    except sqlite3.Error as e:
        print(f"Database error creating announcement '{title}': {e}")
        return None

def get_announcement_by_id(announcement_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single announcement by its ID."""
    announcement = None
    # --- Adjust SQL ---
    sql = """
        SELECT a.*, u.username as creator_username
        FROM announcements a
        LEFT JOIN users u ON a.creator_user_id = u.user_id
        WHERE a.announcement_id = ?;
    """
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (announcement_id,))
            row = cursor.fetchone()
            if row:
                announcement = dict(row)
                # Format date if needed
                created_at = announcement.get('created_at')
                try: announcement['created_at_formatted'] = datetime.datetime.fromisoformat(created_at).strftime('%Y-%m-%d %H:%M') if created_at else 'N/A'
                except: announcement['created_at_formatted'] = created_at
    except sqlite3.Error as e:
        print(f"Database error fetching announcement {announcement_id}: {e}")
    return announcement


def get_all_announcements() -> List[Dict[str, Any]]:
    """Retrieves all announcements (active and inactive) for admin management."""
    announcements = []
    # --- Adjust SQL ---
    sql = """
        SELECT a.*, u.username as creator_username
        FROM announcements a
        LEFT JOIN users u ON a.creator_user_id = u.user_id
        ORDER BY a.created_at DESC;
    """
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            announcements = [dict(row) for row in rows]
            # Format dates
            for ann in announcements:
                 created_at = ann.get('created_at')
                 try: ann['created_at_formatted'] = datetime.datetime.fromisoformat(created_at).strftime('%Y-%m-%d %H:%M') if created_at else 'N/A'
                 except: ann['created_at_formatted'] = created_at
    except sqlite3.Error as e:
        print(f"Database error fetching all announcements: {e}")
    return announcements


def update_announcement(announcement_id: int, title: str, content: str,
                        audience_role: str, target_grade_id: Optional[int],
                        target_section_letter: Optional[str], is_active: bool) -> bool:
    """Updates an existing announcement."""
    # Add validation similar to create_announcement
    if not title or not title.strip() or not content or not content.strip(): return False
    if audience_role not in ['all', 'student', 'teacher', 'admin']: audience_role = 'all'
    if target_section_letter and (len(target_section_letter) != 1 or not 'A' <= target_section_letter.upper() <= 'Z'): target_section_letter = None
    elif target_section_letter: target_section_letter = target_section_letter.upper()
    active_int = 1 if is_active else 0

    # --- Adjust SQL ---
    sql = """
        UPDATE announcements SET
            title = ?, content = ?, audience_role = ?, target_grade_id = ?,
            target_section_letter = ?, is_active = ?
        WHERE announcement_id = ?;
    """
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (title.strip(), content.strip(), audience_role, target_grade_id,
                                 target_section_letter, active_int, announcement_id))
            conn.commit()
            if cursor.rowcount > 0:
                print(f"Announcement {announcement_id} updated successfully.")
                return True
            else:
                print(f"Warning: Announcement {announcement_id} not found for update.")
                return False # Indicate row not found
    except sqlite3.Error as e:
        print(f"Database error updating announcement {announcement_id}: {e}")
        return False


def delete_announcement(announcement_id: int) -> bool:
    """Deletes an announcement by its ID."""
    # --- Adjust SQL ---
    sql = "DELETE FROM announcements WHERE announcement_id = ?;"
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (announcement_id,))
            conn.commit()
            if cursor.rowcount > 0:
                print(f"Announcement {announcement_id} deleted successfully.")
                return True
            else:
                print(f"Warning: Announcement {announcement_id} not found for deletion.")
                return False # Indicate row not found
    except sqlite3.Error as e:
        print(f"Database error deleting announcement {announcement_id}: {e}")
        return False


def get_announcements_for_user(user_id: int, role: str, grade_id: Optional[int] = None, section_letter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves relevant ACTIVE announcements for a specific user based on their role
    and grade/section assignment.
    """
    import datetime
    import sqlite3
    from typing import List, Dict, Any, Optional
    from flask import current_app
    import sys

    announcements = []

    # Step 1: Get assignment info for students
    if role == 'student':
        try:
            from . import student_manager
            if hasattr(student_manager, 'get_student_current_assignment_details'):
                student_assignment = student_manager.get_student_current_assignment_details(user_id)
                if student_assignment:
                    grade_id = student_assignment.get('grade_id')
                    section_letter = student_assignment.get('section_letter')
                else:
                    current_app.logger.debug(f"Student {user_id} has no assignment.")
            else:
                current_app.logger.warning("student_manager.get_student_current_assignment_details not found.")
        except ImportError:
            current_app.logger.warning("Failed to import student_manager for assignment lookup.")
        except Exception as e:
            current_app.logger.error(f"Error fetching assignment for user {user_id}: {e}")

    # Step 2: Build SQL
    base_sql = """
        SELECT a.*, u.username as creator_username
        FROM announcements a
        LEFT JOIN users u ON a.creator_user_id = u.user_id
        WHERE a.is_active = 1
          AND (a.audience_role = 'all' OR a.audience_role = ?)
    """
    params = [role]

    if grade_id is not None:
        base_sql += """
          AND (a.target_grade_id IS NULL OR a.target_grade_id = ?)
          AND (a.target_section_letter IS NULL OR (a.target_grade_id = ? AND a.target_section_letter = ?))
        """
        params.extend([grade_id, grade_id, section_letter])
    else:
        base_sql += " AND a.target_grade_id IS NULL"

    base_sql += " ORDER BY a.created_at DESC;"

    # Step 3: Execute
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(base_sql, params)
            rows = cursor.fetchall()
            announcements = [dict(row) for row in rows]
            for ann in announcements:
                try:
                    ann['created_at_formatted'] = datetime.datetime.fromisoformat(
                        ann.get('created_at')
                    ).strftime('%Y-%m-%d %H:%M') if ann.get('created_at') else 'N/A'
                except:
                    ann['created_at_formatted'] = ann.get('created_at')
    except sqlite3.Error as e:
        current_app.logger.error(f"DB error fetching announcements for {user_id} ({role}): {e}")
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {e}", exc_info=True)

    current_app.logger.debug(f"Found {len(announcements)} announcements for user {user_id} ({role})")
    return announcements




def bulk_create_users_from_excel(file_path):
    """
    Reads an Excel file to create users and assign students to sections.
    Looks for optional columns: subject_name, category_name, grade_name, section_name.
    """
    try:
        # Use fillna('') to replace empty cells (NaN) with empty strings
        df = pd.read_excel(file_path, engine='openpyxl').fillna('')
    except Exception as e:
        return {'success_count': 0, 'failed_rows': [], 'error': f"Could not read the Excel file: {e}"}

    required_columns = ['username', 'email', 'role', 'password']
    if not all(col in df.columns for col in required_columns):
        missing = [col for col in required_columns if col not in df.columns]
        return {'success_count': 0, 'failed_rows': [], 'error': f"Missing required columns: {', '.join(missing)}"}

    # --- Pre-fetch curriculum data for efficient lookup ---
    try:
        # Create a more specific lookup dictionary for grades
        all_grades = student_manager.get_all_grades_for_selection()
        grade_lookup = {
            (str(g['subject_name']).lower(), str(g['category_name']).lower(), str(g['grade_name']).lower()): g['grade_id']
            for g in all_grades
        }
    except Exception as e:
        return {'success_count': 0, 'failed_rows': [], 'error': f"Database error fetching curriculum structure: {e}"}

    success_count = 0
    failed_rows = []

    for index, row in df.iterrows():
        username = str(row.get('username', '')).strip()
        email = str(row.get('email', '')).strip()
        role = str(row.get('role', '')).strip().lower()
        password = str(row.get('password', '')).strip()
        full_name = str(row.get('full_name', username)).strip()
        
        # --- Get optional assignment data ---
        subject_name = str(row.get('subject_name', '')).strip()
        category_name = str(row.get('category_name', '')).strip() # <-- NEW
        grade_name = str(row.get('grade_name', '')).strip()
        section_name = str(row.get('section_name', '')).strip().upper()

        # Basic validation
        if not all([username, email, role, password]):
            failed_rows.append({'row': index + 2, 'username': username, 'reason': 'Missing required data.'})
            continue
        if role not in ['student', 'teacher']:
            failed_rows.append({'row': index + 2, 'username': username, 'reason': f"Invalid role: '{role}'."})
            continue

        try:
            new_user_id = create_user(username=username, password=password, role=role, full_name=full_name, email=email)

            if not new_user_id:
                failed_rows.append({'row': index + 2, 'username': username, 'reason': 'Username or email already exists.'})
                continue

            if role == 'student':
                student_profile_id = student_manager.add_student(name=full_name, user_id=new_user_id)
                if not student_profile_id:
                    failed_rows.append({'row': index + 2, 'username': username, 'reason': 'User created, but failed to create student profile.'})
                    continue

                if all([subject_name, category_name, grade_name, section_name]):
                    # Use the new, more specific lookup key
                    lookup_key = (subject_name.lower(), category_name.lower(), grade_name.lower())
                    grade_id = grade_lookup.get(lookup_key)
                    
                    if not grade_id:
                        failed_rows.append({'row': index + 2, 'username': username, 'reason': f"Combination not found: S: '{subject_name}', C: '{category_name}', G: '{grade_name}'."})
                        continue
                    
                    if not student_manager.assign_student_to_grade_section(student_profile_id, grade_id, section_name):
                        failed_rows.append({'row': index + 2, 'username': username, 'reason': 'Could not assign to section (DB error).'})
                        continue
            
            success_count += 1

        except Exception as e:
            failed_rows.append({'row': index + 2, 'username': username, 'reason': f'Unexpected error: {e}'})

    return {'success_count': success_count, 'failed_rows': failed_rows, 'error': None}




# In src/auth_manager.py, replace the get_teacher_performance_summary function

def get_teacher_performance_summary():
    """
    Fetches all teachers and counts the number of students in the sections
    they are assigned to.
    FIX: This version correctly joins all assignment tables.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT
            u.user_id,
            u.username AS full_name,
            COUNT(DISTINCT sgsa.student_id) as student_count
        FROM users u
        LEFT JOIN teacher_grade_section_assignments tgsa ON u.user_id = tgsa.teacher_user_id
        LEFT JOIN student_grade_section_assignments sgsa ON tgsa.section_id = sgsa.section_id
        WHERE u.role = 'teacher'
        GROUP BY u.user_id, u.username
        ORDER BY u.username;
    """
    try:
        cursor.execute(query)
        teachers_summary = cursor.fetchall()
        return [dict(row) for row in teachers_summary] if teachers_summary else []
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f"Error fetching teacher performance summary: {e}")
        except (ImportError, RuntimeError):
            print(f"ERROR: Could not fetch teacher performance summary. Reason: {e}")
        return []
    finally:
        conn.close()



# Add this new function to the end of src/auth_manager.py

def get_assigned_teacher_ids_for_section(section_id):
    """
    Fetches a set of teacher user IDs assigned to a specific section.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT teacher_user_id FROM teacher_grade_section_assignments WHERE section_id = ?"
    try:
        cursor.execute(query, (section_id,))
        rows = cursor.fetchall()
        # Return a set for efficient lookup, e.g., {20, 25}
        return {row['teacher_user_id'] for row in rows} if rows else set()
    except Exception as e:
        print(f"DB error fetching assigned teacher IDs for section {section_id}: {e}")
        return set()
    finally:
        conn.close()




# In src/auth_manager.py, add this new function at the end.

def get_assigned_grades_for_teacher(teacher_user_id):
    """
    Fetches a simple list of all unique grades a teacher is assigned to.
    This is used to populate dropdown menus for the teacher.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # This query joins assignments with grades, categories, and subjects
    # to get the full, descriptive name for each grade.
    query = """
        SELECT DISTINCT
            g.grade_id,
            g.grade_name,
            cat.category_name,
            sub.subject_name
        FROM teacher_grade_section_assignments tgsa
        JOIN grades g ON tgsa.grade_id = g.grade_id
        JOIN categories cat ON g.category_id = cat.category_id
        JOIN subjects sub ON cat.subject_id = sub.subject_id
        WHERE tgsa.teacher_user_id = ?
        ORDER BY sub.subject_name, cat.category_name, g.grade_name;
    """
    try:
        cursor.execute(query, (teacher_user_id,))
        grades = cursor.fetchall()
        return [dict(row) for row in grades] if grades else []
    except Exception as e:
        print(f"DB error fetching assigned grades for teacher {teacher_user_id}: {e}")
        return []
    finally:
        conn.close()