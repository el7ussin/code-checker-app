# Add these functions to src/student_manager.py (or game_manager.py)

# --- Memory Match Game - Admin Functions ---

def add_memory_match_pair(category: str, item1_text: str, item2_text: str,
                          difficulty: int = 1, is_active: bool = True,
                          created_by_user_id: Optional[int] = None) -> Optional[int]:
    """Adds a new pair of items for the memory match game."""
    # Basic validation
    if not all([category, item1_text, item2_text]):
        print("Error: Category, Item 1, and Item 2 text cannot be empty.")
        return None
    category = category.strip()
    item1_text = item1_text.strip()
    item2_text = item2_text.strip()
    active_int = 1 if is_active else 0
    difficulty = difficulty if isinstance(difficulty, int) and difficulty > 0 else 1

    # --- Adjust table/column names ---
    sql = """
        INSERT INTO memory_match_pairs
               (category, item1_text, item2_text, difficulty, is_active, created_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?);
    """
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (category, item1_text, item2_text, difficulty, active_int, created_by_user_id))
            conn.commit()
            new_id = cursor.lastrowid
            print(f"Memory match pair added ID:{new_id} Category:{category}")
            return new_id
    except sqlite3.Error as e:
        print(f"Database error adding memory match pair: {e}")
        return None

def get_all_memory_match_pairs() -> List[Dict[str, Any]]:
    """Retrieves all memory match pairs, ordered by category."""
    pairs = []
    # --- Adjust table/column names ---
    sql = """
        SELECT pair_id, category, item1_text, item2_text, difficulty, is_active, created_at
        FROM memory_match_pairs
        ORDER BY category, pair_id;
    """
    # --- End Adjust ---
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            pairs = [dict(row) for row in rows]
            # Optional: Format created_at date here if needed
            for pair in pairs:
                 created_at_str = pair.get('created_at')
                 try: pair['created_at_formatted'] = datetime.datetime.fromisoformat(created_at_str).strftime('%Y-%m-%d %H:%M') if created_at_str else "N/A"
                 except: pair['created_at_formatted'] = created_at_str
    except sqlite3.Error as e:
        print(f"Database error fetching memory match pairs: {e}")
    return pairs

# TODO later: get_memory_match_pair_by_id, update_memory_match_pair, delete_memory_match_pair

# --- End Memory Match Game Functions ---