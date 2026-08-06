import os
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
from sqlalchemy import create_engine

# ---------------------------------------------------------------------------
# Config — set these via app.yaml env vars
# ---------------------------------------------------------------------------
# Read connection components from environment variables
LAKEBASE_HOST = os.environ.get("LAKEBASE_HOST")
LAKEBASE_USER = os.environ.get("LAKEBASE_USER")
LAKEBASE_PASSWORD = os.environ.get("LAKEBASE_PASSWORD")
LAKEBASE_DATABASE = os.environ.get("LAKEBASE_DATABASE")

# Validate required environment variables
if not all([LAKEBASE_HOST, LAKEBASE_USER, LAKEBASE_PASSWORD, LAKEBASE_DATABASE]):
    missing = [k for k, v in {
        "LAKEBASE_HOST": LAKEBASE_HOST,
        "LAKEBASE_USER": LAKEBASE_USER,
        "LAKEBASE_PASSWORD": LAKEBASE_PASSWORD,
        "LAKEBASE_DATABASE": LAKEBASE_DATABASE
    }.items() if not v]
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

# Build connection string with URL encoding for special characters
from urllib.parse import quote_plus
db_url = f"postgresql://{quote_plus(LAKEBASE_USER)}:{quote_plus(LAKEBASE_PASSWORD)}@{LAKEBASE_HOST}/{LAKEBASE_DATABASE}?sslmode=require"

# Option A: SQLAlchemy Connection
engine = create_engine(db_url)

# Option B: Direct Psycopg2 Connection (used by get_connection())
# Connection will be created on-demand by get_connection()

# ---------------------------------------------------------------------------
# Connection Helper
# ---------------------------------------------------------------------------

def get_connection():
    """Get a database connection using psycopg2."""
    return psycopg2.connect(db_url)

# ---------------------------------------------------------------------------
# Ticket Functions
# ---------------------------------------------------------------------------

def get_all_tickets(status_filter=None):
    """Fetch all support tickets from the database, optionally filtered by status."""
    conn = get_connection()
    try:
        if status_filter and status_filter != "all":
            query = "SELECT * FROM ai_support.tickets WHERE status = %s ORDER BY created_at DESC"
            df = pd.read_sql(query, conn, params=(status_filter,))
        else:
            query = "SELECT * FROM ai_support.tickets ORDER BY created_at DESC"
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Error loading tickets: {str(e)}")
        raise
    finally:
        conn.close()


def get_ticket_by_id(ticket_id):
    """Fetch a specific ticket by ID."""
    conn = get_connection()
    try:
        query = "SELECT * FROM ai_support.tickets WHERE ticket_id = %s"
        df = pd.read_sql(query, conn, params=(ticket_id,))
        return df.iloc[0] if len(df) > 0 else None
    finally:
        conn.close()


def get_ticket_messages(ticket_id):
    """Fetch all messages for a specific ticket."""
    conn = get_connection()
    try:
        query = "SELECT * FROM ai_support.ticket_messages WHERE ticket_id = %s ORDER BY created_at ASC"
        df = pd.read_sql(query, conn, params=(ticket_id,))
        return df
    finally:
        conn.close()


def create_ticket(title, status, created_by):
    """Create a new support ticket with auto-generated ticket_id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Get the next ticket_id (max + 1)
        cursor.execute("SELECT COALESCE(MAX(ticket_id), 0) + 1 FROM ai_support.tickets")
        new_ticket_id = cursor.fetchone()[0]
        
        # Insert the new ticket (only fields that exist in the table)
        query = """
            INSERT INTO ai_support.tickets (ticket_id, title, status, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING ticket_id
        """
        now = datetime.now()
        cursor.execute(query, (new_ticket_id, title, status, created_by, now))
        ticket_id = cursor.fetchone()[0]
        conn.commit()
        return ticket_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def add_message_to_ticket(ticket_id, message, author="Support Agent"):
    """Add a new message to an existing ticket."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Get the next message_id (max + 1)
        cursor.execute("SELECT COALESCE(MAX(message_id), 0) + 1 FROM ai_support.ticket_messages")
        new_message_id = cursor.fetchone()[0]
        
        query = """
            INSERT INTO ai_support.ticket_messages (message_id, ticket_id, message_text, author, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (new_message_id, ticket_id, message, author, datetime.now()))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def update_ticket_status(ticket_id, new_status):
    """Update the status of a ticket."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "UPDATE ai_support.tickets SET status = %s WHERE ticket_id = %s"
        cursor.execute(query, (new_status, ticket_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def show_ticket_list():
    """Display list of all tickets."""
    # Initialize status filter in session state
    if "status_filter" not in st.session_state:
        st.session_state.status_filter = "all"
    
    # Status filter buttons
    st.subheader("Filter by Status")
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 3])
    
    with col1:
        if st.button("🔵 All", use_container_width=True, type="primary" if st.session_state.status_filter == "all" else "secondary"):
            st.session_state.status_filter = "all"
            st.rerun()
    
    with col2:
        if st.button("🟢 Open", use_container_width=True, type="primary" if st.session_state.status_filter == "open" else "secondary"):
            st.session_state.status_filter = "open"
            st.rerun()
    
    with col3:
        if st.button("🟡 In Progress", use_container_width=True, type="primary" if st.session_state.status_filter == "in_progress" else "secondary"):
            st.session_state.status_filter = "in_progress"
            st.rerun()
    
    with col4:
        if st.button("✅ Resolved", use_container_width=True, type="primary" if st.session_state.status_filter == "resolved" else "secondary"):
            st.session_state.status_filter = "resolved"
            st.rerun()
    
    st.divider()
    
    # Get filtered tickets
    try:
        tickets_df = get_all_tickets(status_filter=st.session_state.status_filter)
        
        if len(tickets_df) == 0:
            st.info("No tickets found.")
            return
        
        # Column headers
        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
        with col1:
            st.markdown("<p style='font-size:18px; font-weight:bold;'>Ticket ID</p>", unsafe_allow_html=True)
        with col2:
            st.markdown("<p style='font-size:18px; font-weight:bold;'>Title</p>", unsafe_allow_html=True)
        with col3:
            st.markdown("<p style='font-size:18px; font-weight:bold;'>Status</p>", unsafe_allow_html=True)
        with col4:
            st.markdown("<p style='font-size:18px; font-weight:bold;'>Update Status</p>", unsafe_allow_html=True)
        with col5:
            st.markdown("<p style='font-size:18px; font-weight:bold;'>Created</p>", unsafe_allow_html=True)
        
        st.divider()
        
        # Display tickets with clickable IDs and status update
        for _, ticket in tickets_df.iterrows():
            ticket_id = ticket['ticket_id']
            current_status = ticket.get('status', 'open')
            
            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
            
            with col1:
                if st.button(f"#{ticket_id}", key=f"ticket_{ticket_id}"):
                    st.session_state.selected_ticket_id = ticket_id
                    st.session_state.page = "ticket_detail"
                    st.rerun()
            
            with col2:
                st.write(ticket.get('title', 'Untitled'))
            
            with col3:
                st.write(current_status)
            
            with col4:
                new_status = st.selectbox(
                    "Change status",
                    ["open", "in_progress", "resolved"],
                    index=["open", "in_progress", "resolved"].index(current_status),
                    key=f"status_{ticket_id}",
                    label_visibility="collapsed"
                )
                if new_status != current_status:
                    try:
                        update_ticket_status(ticket_id, new_status)
                        st.success("Status updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating status: {e}")
            
            with col5:
                st.write(str(ticket.get('created_at', ''))[:10])
            
            st.divider()
    
    except Exception as e:
        st.error(f"Error loading tickets: {e}")


def show_ticket_detail():
    """Display detailed view of a selected ticket and its messages."""
    ticket_id = st.session_state.get("selected_ticket_id")
    
    if not ticket_id:
        st.error("No ticket selected.")
        return
    
    # Back button
    if st.button("← Back to Ticket List"):
        st.session_state.page = "ticket_list"
        st.rerun()
    
    try:
        # Get ticket details
        ticket = get_ticket_by_id(ticket_id)
        
        if ticket is None:
            st.error("Ticket not found.")
            return
        
        # Display ticket info
        ticket_id_display = ticket.get('ticket_id', ticket_id)
        ticket_title = ticket.get('title', 'Untitled')
        ticket_status = ticket.get('status', 'Unknown')
        ticket_created = ticket.get('created_at', 'Unknown')
        
        st.header(f"Ticket #{ticket_id_display}: {ticket_title}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Status:** {ticket_status}")
        with col2:
            st.write(f"**Created:** {str(ticket_created)[:19]}")
        
        st.divider()
        
        # Messages section
        st.subheader("Messages")
        
        messages_df = get_ticket_messages(ticket_id)
        
        if len(messages_df) == 0:
            st.info("No messages found for this ticket.")
        else:
            st.write(f"**Total Messages:** {len(messages_df)}")
            st.divider()
            
            # Format the created_at column to remove microseconds
            if 'created_at' in messages_df.columns:
                messages_df['created_at'] = messages_df['created_at'].astype(str).str.slice(0, 19)
            
            # Display all messages as a table
            st.dataframe(
                messages_df,
                use_container_width=True,
                hide_index=True
            )
        
        st.divider()
        
        # Add message form
        st.subheader("✉️ Add New Message")
        with st.form("add_message_form"):
            message = st.text_area("Message*", height=100, placeholder="Type your message here...")
            author = st.text_input("Author*", placeholder="Your name")
            
            if st.form_submit_button("Send Message"):
                if message.strip() and author.strip():
                    try:
                        add_message_to_ticket(ticket_id, message, author)
                        st.success("✅ Message added successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding message: {e}")
                else:
                    st.warning("Please fill in both the message and author fields.")
    
    except Exception as e:
        st.error(f"Error loading ticket: {e}")


def show_create_ticket():
    """Display form to create a new ticket."""
    st.header("➕ Create New Ticket")
    
    with st.form("create_ticket_form_sidebar"):
        title = st.text_input("Title*", placeholder="Brief description of the issue")
        status = st.selectbox("Status*", ["open", "in_progress", "resolved"])
        created_by = st.text_input("Created By*", placeholder="Your name")
        
        st.caption("* Required fields")
        st.caption("Note: ticket_id and created_at will be automatically generated")
        
        if st.form_submit_button("Create Ticket"):
            if title.strip() and status and created_by.strip():
                try:
                    ticket_id = create_ticket(title, status, created_by)
                    st.success(f"Ticket #{ticket_id} created successfully!")
                    st.session_state.selected_ticket_id = ticket_id
                    st.session_state.page = "ticket_detail"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating ticket: {e}")
            else:
                st.warning("Please fill in all required fields (Title, Status, Created By).")


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="AI Tickets Support",
        layout="wide"
    )
    
    # Custom CSS for styling
    st.markdown("""
        <style>
        /* Move main title up */
        .main .block-container {
            padding-top: 2rem !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("AI Tickets Support System")
    
    # Initialize session state
    if "page" not in st.session_state:
        st.session_state.page = "ticket_list"
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    if st.sidebar.button("View All Tickets", use_container_width=True):
        st.session_state.page = "ticket_list"
        st.rerun()
    
    if st.sidebar.button("Create New Ticket", use_container_width=True):
        st.session_state.page = "create_ticket"
        st.rerun()
    
    st.sidebar.divider()
    
    # Page routing
    if st.session_state.page == "ticket_list":
        show_ticket_list()
    elif st.session_state.page == "ticket_detail":
        show_ticket_detail()
    elif st.session_state.page == "create_ticket":
        show_create_ticket()


if __name__ == "__main__":
    main()
