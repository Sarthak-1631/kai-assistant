import os
import time
import subprocess
import threading
import datetime
import re
import queue
import pyperclip
from google import genai
from google.genai import types
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from pynput import keyboard
from dotenv import load_dotenv

load_dotenv()


chat_lock = threading.Lock()

# 1. Setup

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("System Alert: GOOGLE_API_KEY environment variable not set.")
    print("Run: export GOOGLE_API_KEY='your_key' in your terminal before running.")
    exit(1)

VAULT_PATH = "/Users/sarthaksharma/Memory" 
client = genai.Client() 


# 2. Vector Setup for Semantic Search

DB_PATH = os.path.join(VAULT_PATH, ".chroma_db")
chroma_client = chromadb.PersistentClient(path=DB_PATH)

try:
    gemini_ef = embedding_functions.GoogleGeminiEmbeddingFunction(
        model_name="models/text-embedding-004"
    )
    collection = chroma_client.get_or_create_collection(
        name="kai_vault",
        embedding_function=gemini_ef
    )
except Exception as e:
    print(f"System Alert [Vector DB]: Could not initialize embedding function. {e}")

# 3. Audio

speech_queue = queue.Queue()

def clean_markdown_for_speech(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'```.*?```', ' code block omitted ', text, flags=re.DOTALL) 
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text) 
    text = re.sub(r'[*#_`]', '', text) 
    text = re.sub(r'\n+', ' . ', text) 
    return text.strip()

def _speech_worker():
    """Dedicated background worker that plays audio sequentially from the queue."""
    while True:
        text = speech_queue.get()
        if text is None:
            break
        clean_text = clean_markdown_for_speech(text)
        if clean_text:
            try:
                subprocess.run(["say", "-v", "Daniel", "-r", "200", clean_text])
            except Exception as e:
                print(f"\nSystem Alert [Audio Module]: {str(e)}")
        speech_queue.task_done()


speech_thread = threading.Thread(target=_speech_worker, daemon=True)
speech_thread.start()

def speak(text: str):
    """Enqueues text to be spoken sequentially without overlapping."""
    if text:
        speech_queue.put(text)

# 4. Kai Tools

def secure_path(filename: str) -> str:
    filepath = os.path.abspath(os.path.join(VAULT_PATH, filename))
    if not filepath.startswith(os.path.abspath(VAULT_PATH)):
        raise ValueError("Security Alert: Path traversal attempt blocked.")
    return filepath

def read_vault_note(filename: str) -> str:
    try:
        filepath = secure_path(filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"System Alert: File {filename} not found."
    except Exception as e:
        return f"System Alert: {str(e)}"

def update_memory(content: str) -> str:
    try:
        filepath = secure_path("MEMORY.md")
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"\n- {content}")
        index_vault()
        return "Diagnostic recorded to permanent memory and indexed."
    except Exception as e:
        return f"System Alert: Could not update memory. {str(e)}"

def scan_directory(folder_path: str = "") -> str:
    try:
        target_dir = secure_path(folder_path)
        files = os.listdir(target_dir)
        md_files = [f for f in files if f.endswith('.md') or os.path.isdir(os.path.join(target_dir, f))]
        return f"Contents of '{folder_path}':\n" + "\n".join(md_files)
    except FileNotFoundError:
        return f"System Alert: Directory '{folder_path}' not found."
    except Exception as e:
        return f"System Alert: {str(e)}"

def run_terminal_command(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return f"Command executed successfully. Output:\n{result.stdout}"
        else:
            return f"Command failed. Error:\n{result.stderr}"
    except Exception as e:
        return f"System Alert: Execution failed with error {str(e)}"

def append_to_daily_note(content: str) -> str:
    """Appends content to today's Daily Note in Obsidian, creating it if necessary."""
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"{today}.md"
        filepath = secure_path(filename)
        
        timestamp = datetime.datetime.now().strftime("%H:%M")
        entry = f"\n- **{timestamp}**: {content}"
        

        is_new_file = not os.path.exists(filepath) or os.path.getsize(filepath) == 0
        
        with open(filepath, 'a', encoding='utf-8') as f:
            if is_new_file:
                f.write(f"# Daily Note: {today}\n")
            f.write(entry)
            
  
        index_vault() 
        return f"System Alert: Logged successfully to {filename} at {timestamp}."
    except Exception as e:
        return f"System Alert: Could not update Daily Note. {str(e)}"


def open_mac_app(app_name: str) -> str:
    try:
        subprocess.run(["open", "-a", app_name])
        return f"System Alert: {app_name} opened successfully."
    except Exception as e:
        return f"System Alert: Failed to open {app_name}. {str(e)}"

def read_clipboard() -> str:
    try:
        return f"Clipboard contents:\n{pyperclip.paste()}"
    except Exception as e:
        return f"System Alert: Could not read clipboard. {str(e)}"


def write_system_file(filepath: str, content: str) -> str:
    """Creates or overwrites a file on the local macOS system. Use this to build scripts, web files, or configs."""

    absolute_path = os.path.abspath(os.path.expanduser(filepath))
    
    print(f"\n[SECURITY OVERRIDE REQUIRED]")
    print(f"Kai is requesting permission to write to: {absolute_path}")
    print(f"--- CONTENT PREVIEW ---\n{content[:150]}...\n-----------------------")
    

    confirmation = input("Allow execution? (y/n): ")
    
    if confirmation.strip().lower() == 'y':
        try:
          
            os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
            with open(absolute_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"System Alert: File successfully written to {absolute_path}"
        except Exception as e:
            return f"System Alert [Write Failed]: {str(e)}"
    else:
        return "System Alert: User denied file modification. Action aborted."


# 5. Semantic Search Modules


def index_vault() -> str:
    """Indexes all markdown files in the vault, embedding only those modified since the last run."""
    try:
        documents = []
        ids = []
        metadatas = []
        
 
        existing_data = collection.get(include=['metadatas'])
        existing_mtimes = {}
        
 
        if existing_data and existing_data.get('ids'):
            for doc_id, meta in zip(existing_data['ids'], existing_data['metadatas']):
                if meta and "mtime" in meta:
                    existing_mtimes[doc_id] = meta["mtime"]

 
        for root, _, files in os.walk(VAULT_PATH):
            if ".chroma_db" in root:
                continue
            for f in files:
                if f.endswith('.md'):
                    filepath = os.path.join(root, f)
                    rel_path = os.path.relpath(filepath, VAULT_PATH)
                    current_mtime = os.path.getmtime(filepath)
                    

                    if rel_path not in existing_mtimes or current_mtime > existing_mtimes[rel_path]:
                        with open(filepath, 'r', encoding='utf-8') as file:
                            documents.append(file.read())
                            ids.append(rel_path)
                            metadatas.append({"mtime": current_mtime})
        
        if documents:
            collection.upsert(
                documents=documents,
                ids=ids,
                metadatas=metadatas
            )
            return f"Successfully indexed {len(documents)} new or modified files."
        
        return "Vault index is already up to date. No new modifications found."
    except Exception as e:
        return f"System Alert [Indexing Failed]: {str(e)}"
    
def semantic_search(query: str) -> str:
    """Searches the vault conceptually for a given topic or idea."""
    try:
        results = collection.query(
            query_texts=[query],
            n_results=3
        )
        
        if not results['documents'] or not results['documents'][0]:
            return "No relevant notes found."
            
        response = "Semantic Search Results:\n\n"
        for i, doc in enumerate(results['documents'][0]):
            source_id = results['ids'][0][i]
            response += f"--- Source: {source_id} ---\n{doc}\n\n"
        return response
    except Exception as e:
        return f"System Alert [Search Failed]: {str(e)}"


# 6. Sleep Cycle

def consolidate_memory():
    print("\nKai: Initiating memory consolidation (Sleep Cycle)...")
    try:
        memory_path = secure_path("MEMORY.md")
        if not os.path.exists(memory_path):
            return
            
        with open(memory_path, 'r', encoding='utf-8') as f:
            memory_content = f.read()

        if len(memory_content.strip()) < 50:
            print("Kai: Memory log minimal. No consolidation required.")
            return

        print("Kai: Synthesizing recent diagnostics...")
        summary_prompt = (
            "Summarize the following memory logs into a dense set of core facts about the user and the system. "
            "Extract only the most critical, long-term insights and drop redundant or short-term information. "
            f"Format as concise Markdown bullet points.\n\nMemories:\n{memory_content}"
        )
        
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=summary_prompt
        )
        
        core_path = secure_path("CORE-IDENTITY.md")
        with open(core_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{response.text}\n")
            
        with open(memory_path, 'w', encoding='utf-8') as f:
            f.write("# Kai Memory Diagnostics\n\n")
            
        index_vault()
        print("Kai: Diagnostics synthesized and recorded to CORE-IDENTITY.md.")
        
    except Exception as e:
        print(f"System Alert [Sleep Cycle Error]: {str(e)}")


# 7. Boot Sequence

def initialize_vault():
    os.makedirs(VAULT_PATH, exist_ok=True)
    
    defaults = {
        "MEMORY.md": "# Kai Memory Diagnostics\n\n",
        "CORE-IDENTITY.md": "# Kai & User Core Identity\n\n",
        "KAI-BOOT.md": "You are Kai, an advanced E.V. architecture AI assistant. Be concise, analytical, and helpful.\n",
        "VAULT-INDEX.md": "# Vault Index\nRoot directory active.\n"
    }
    
    for filename, content in defaults.items():
        filepath = os.path.join(VAULT_PATH, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

def boot_kai():
    print("Booting Kai (E.V. Architecture)...")
    initialize_vault()
    
 
    print("Kai: Indexing vault vectors...")
    index_vault()
    
    system_prompt = read_vault_note("KAI-BOOT.md")
    

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_prompt += f"\n\nCurrent System Time: {current_time}"
    
    core_identity = read_vault_note("CORE-IDENTITY.md")
    vault_index = read_vault_note("VAULT-INDEX.md")
    
    instruction = f"{system_prompt}\n\nCore Identity & Long-Term Context:\n{core_identity}\n\nHere is the map of your memory vault:\n{vault_index}"
    
    chat = client.chats.create(
        model="gemini-3.5-flash-lite", 
        config=types.GenerateContentConfig(
            system_instruction=instruction,
            tools=[
                read_vault_note, 
                update_memory, 
                scan_directory, 
                run_terminal_command, 
                open_mac_app, 
                read_clipboard,
                index_vault,
                semantic_search,
                append_to_daily_note,
                write_system_file
            ],
            temperature=0.3
        )
    )
    return chat


def on_queue_hotkey():
    """Triggered globally when Cmd+Ctrl+Q is pressed to manually check the queue."""
    subprocess.Popen(["afplay", "/System/Library/Sounds/Tink.aiff"])
    print("\n[Global Trigger] Manual queue check initiated...")

    threading.Thread(target=process_task_queue, args=(chat,), daemon=True).start()


def process_task_queue(chat_session):
    print("\nKai: Checking task queue...")
    queue_path = secure_path("KAI-QUEUE.md")
    
 
    if not os.path.exists(queue_path):
        with open(queue_path, 'w', encoding='utf-8') as f:
            f.write("# Kai Task Queue\n\nAdd tasks below using `- [ ] Task description`\n")
        print("Kai: No tasks found. KAI-QUEUE.md created.")
        return

    with open(queue_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tasks_completed = 0
    for i, line in enumerate(lines):
        # Look for standard markdown unchecked boxes
        if line.lstrip().startswith("- [ ]"):
            # Extract the actual task instruction
            task_instruction = line.split("- [ ]")[1].strip()
            
            print(f"\n[Task Queue] Executing: {task_instruction}")
            speak("Executing assigned task.")
            
            try:
  
                with chat_lock:
                    prompt = (
                        f"SYSTEM AUTOMATION INITIATED:\n"
                        f"You are executing a background task from the queue. "
                        f"Complete this objective silently or with minimal explanation, "
                        f"using your tools if necessary:\n{task_instruction}"
                    )
                    response = chat_session.send_message(prompt)
                    
                print(f"Kai: {response.text}")
                
 
                lines[i] = line.replace("- [ ]", "- [x]", 1)
                tasks_completed += 1
                
            except Exception as e:
                print(f"System Alert [Queue Execution Failed]: {str(e)}")


    if tasks_completed > 0:
        with open(queue_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"\nKai: Completed {tasks_completed} queued tasks and updated KAI-QUEUE.md.")
        speak(f"Task queue processing complete. {tasks_completed} tasks handled.")
    else:
        print("Kai: Task queue is empty.")




# 8. Terminal interface

if __name__ == "__main__":
    chat = boot_kai()

    
    startup_msg = "Kai is online. Systems calibrated. Waiting for input..."
    print(f"\n{startup_msg}\n")
    speak("Kai is online. Systems calibrated.")

    hotkey_listener = keyboard.GlobalHotKeys({
        '<cmd>+<ctrl>+k': on_queue_hotkey
    })
    hotkey_listener.start()
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.strip().lower() in ['exit', 'quit']:
                print("Kai: Shutting down systems.")
                speak("Shutting down systems.")
                consolidate_memory()
                break
            
            with chat_lock:
                response = chat.send_message(user_input)
            
            print(f"\nKai: {response.text}\n")
            speak(response.text)
            
        except KeyboardInterrupt:
            print("\nKai: Manual override detected. Shutting down.")
            consolidate_memory()
            break
        except Exception as e:
            print(f"\nSystem Error: {str(e)}\n")
