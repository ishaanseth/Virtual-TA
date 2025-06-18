# main.py
from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

# --- AI Pipe Client ---
embedding_client = OpenAI(
    api_key=os.getenv("AIPIPE_TOKEN"),
    base_url=os.getenv("OPENAI_API_BASE_FOR_EMBEDDINGS"),
)
chat_client = OpenAI(
    api_key=os.getenv("AIPIPE_TOKEN"),
    base_url=os.getenv("OPENROUTER_API_BASE_FOR_CHAT"),
)

# --- Embeddings and Vector Store ---
all_content_embeddings = []
EMBEDDINGS_FILE = "content_embeddings.json"

discourse_topics_map = {}  # topic_id -> list of posts sorted by post_number


def find_top_n_similar(query_embedding, content_embeddings_list, top_n=5):
    if not query_embedding or not content_embeddings_list:
        return []
    query_embedding_reshaped = np.array(query_embedding).reshape(1, -1)
    similarities = []
    for content_emb_vector, data_object in content_embeddings_list:
        content_emb_vector_reshaped = np.array(content_emb_vector).reshape(1, -1)
        sim = cosine_similarity(query_embedding_reshaped, content_emb_vector_reshaped)[
            0
        ][0]
        similarities.append((sim, data_object))
    similarities.sort(key=lambda x: x[0], reverse=True)
    return [data_object for sim, data_object in similarities[:top_n]]


async def generate_llm_answer(user_question: str, contexts: list):
    if not contexts:
        return "I couldn't find any relevant documents to answer your question."

    prompt_context_str = ""
    for i, ctx in enumerate(contexts):
        url = str(ctx.get("url", "N/A"))
        content = str(ctx.get("content", "No content available")).strip()
        title = str(ctx.get("title", "Untitled Document")).strip()
        source_type = str(ctx.get("source", "Unknown source")).strip()
        max_context_len = 500
        if len(content) > max_context_len:
            content = content[:max_context_len] + "..."
        prompt_context_str += f'Context Document {i+1} (Source Type: {source_type}, Title: "{title}", URL: {url}):\n{content}\n\n'

    system_message = """You are a helpful Teaching Assistant for the 'Tools in Data Science' (TDS) course.
    Your goal is to answer student questions accurately based ONLY on the provided context documents.
    Do not use any external knowledge or make assumptions beyond what is in the context.
    If the answer is found in the context, clearly state the answer and try to be concise.
    After providing information from a specific context document, cite its URL in square brackets, for example: [Source URL: http://example.com/page].
    If multiple documents support an answer, you can cite them together like [Source URL1: ..., Source URL2: ...].
    If the provided context documents do not contain the answer to the question, you MUST respond with "I could not find an answer to your question in the provided materials."
    Do not try to answer if the context is insufficient."""

    user_prompt = f"""Here are the relevant context documents:

    {prompt_context_str}

    Based ONLY on the context documents above, please answer the following student question:
    Student Question: "{user_question}"
    """

    try:
        print(f"\n--- LLM Call ---")
        print(f"System Message for LLM: {system_message}")
        print(
            f"User Prompt for LLM (context part snippet):\n{prompt_context_str[:300]}..."
        )
        print(f"User Prompt for LLM (question part): {user_question}")

        chat_completion = chat_client.chat.completions.create(
            model=os.getenv("CHAT_MODEL_NAME"),  # type: ignore
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        answer = chat_completion.choices[0].message.content
        print(f"LLM Raw Answer: {answer[:300]}...")  # type: ignore # Log LLM answer snippet
        return answer.strip() if answer else "Error: Empty response from LLM."
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return "Sorry, I encountered an error trying to generate an answer."


class QuestionRequest(BaseModel):
    question: str
    image: str | None = None


class Link(BaseModel):
    url: str
    text: str


class AnswerResponse(BaseModel):
    answer: str
    links: list[Link]


app = FastAPI()


def get_embedding(text_to_embed: str):
    try:
        response = embedding_client.embeddings.create(
            model=os.getenv("EMBEDDING_MODEL_NAME"),  # type: ignore
            input=text_to_embed,
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding for text '{text_to_embed[:50]}...': {e}")
        return None


@app.on_event("startup")
async def startup_event():
    global course_content_data, discourse_posts_data, all_content_embeddings
    print("Loading data...")
    course_content_data = []
    discourse_posts_data = []

    try:
        with open("course_content.json", "r", encoding="utf-8") as f:
            course_content_data = json.load(f)
        print(f"Loaded {len(course_content_data)} items from course_content.json")
    except FileNotFoundError:
        print("Error: course_content.json not found.")
    except json.JSONDecodeError:
        print("Error: Could not decode course_content.json.")

    try:
        with open("discourse_posts.json", "r", encoding="utf-8") as f:
            discourse_posts_data = json.load(f)
        print(f"Loaded {len(discourse_posts_data)} items from discourse_posts.json")
    except FileNotFoundError:
        print("Error: discourse_posts.json not found.")
    except json.JSONDecodeError:
        print("Error: Could not decode discourse_posts.json.")

    print("AI Pipe clients configured (using environment variables).")
    loaded_from_file = False
    try:
        if os.path.exists(EMBEDDINGS_FILE):
            with open(EMBEDDINGS_FILE, "r") as f:
                loaded_embeddings_data = json.load(f)
                all_content_embeddings = [
                    (item["embedding"], item["data"]) for item in loaded_embeddings_data
                ]
            print(
                f"Loaded {len(all_content_embeddings)} pre-computed embeddings from {EMBEDDINGS_FILE}"
            )
            if all_content_embeddings:
                loaded_from_file = True
    except Exception as e:
        print(
            f"Could not load pre-computed embeddings from {EMBEDDINGS_FILE}: {e}. Will re-generate."
        )
        all_content_embeddings = []

    if not loaded_from_file:
        print("Generating embeddings for all content (this might take a while)...")
        combined_content = []
        for item in course_content_data:
            text_content = str(
                item.get("content", "")
            )  # Using just content for embedding
            title = str(item.get("title", ""))  # Keep title for original_data
            if text_content:
                combined_content.append(
                    {
                        "text_to_embed": text_content,  # Embed only content
                        "original_data": {
                            "source": "course",
                            "title": title,
                            "content": text_content,
                            "url": item.get("source_url"),
                        },
                    }
                )
        for item in discourse_posts_data:
            text_content = str(
                item.get("content", "")
            )
            topic_id_val = item.get("topic_id", "")
            post_number_val = item.get("post_number", "")
            title = str(item.get("topic_title", ""))
            if text_content:
                combined_content.append(
                    {
                        "text_to_embed": text_content,  # Embed only content
                        "original_data": {
                            "source": "discourse",
                            "title": title,
                            "content": text_content,
                            "url": item.get("url"),
                            "topic_id": topic_id_val,
                            "post_number": post_number_val
                        },
                    }
                )
        all_content_embeddings = []
        for i, content_item in enumerate(combined_content):
            print(
                f"Embedding item {i+1}/{len(combined_content)}: {content_item['original_data']['title'][:50]} (Source: {content_item['original_data']['source']})..."
            )
            embedding_vector = get_embedding(content_item["text_to_embed"])
            if embedding_vector:
                all_content_embeddings.append(
                    (embedding_vector, content_item["original_data"])
                )
            # time.sleep(0.05) # Reduced delay, adjust if rate limits hit

        if combined_content:
            try:
                with open(EMBEDDINGS_FILE, "w") as f:
                    serializable_embeddings = [
                        {"embedding": emb, "data": data}
                        for emb, data in all_content_embeddings
                    ]
                    json.dump(serializable_embeddings, f)
                print(
                    f"Saved {len(all_content_embeddings)} embeddings to {EMBEDDINGS_FILE}"
                )
            except Exception as e:
                print(f"Error saving embeddings: {e}")
    print(f"Total content items with embeddings: {len(all_content_embeddings)}")

    for post in discourse_posts_data:
        topic_id = post.get("topic_id")
        if topic_id not in discourse_topics_map:
            discourse_topics_map[topic_id] = []
        discourse_topics_map[topic_id].append(post)

    # Sort posts within each topic by post_number
    for topic_id in discourse_topics_map:
        discourse_topics_map[topic_id].sort(key=lambda p: p.get("post_number", 0))
    print(f"Discourse topics loaded with {len(discourse_topics_map)} unique topics.")
    print("API ready.")


@app.post("/api/", response_model=AnswerResponse)
async def get_answer(request: QuestionRequest):
    print(f"\n--- New Request ---")  # Separator for logs
    print(f"Received question: {request.question}")

    if not request.question.strip():
        return AnswerResponse(answer="Please provide a question.", links=[])

    question_embedding = get_embedding(request.question)
    if not question_embedding:
        return AnswerResponse(
            answer="Sorry, I couldn't process the question embedding.", links=[]
        )

    # Using top_n=5 as discussed
    initial_relevant_contexts = find_top_n_similar(
        question_embedding, all_content_embeddings, top_n=3
    )

    final_contexts_for_llm = []
    processed_urls = set()  # To avoid adding the same post multiple times

    # --- ADDED LOGGING FOR RETRIEVED CONTEXTS ---
    print(
        f"\nRetrieved {len(initial_relevant_contexts)} contexts for question: '{request.question}'"
    )
    for ctx in initial_relevant_contexts:
        if ctx["url"] not in processed_urls:
            final_contexts_for_llm.append(ctx)
            processed_urls.add(ctx["url"])

        if ctx.get("source") == "discourse":
            topic_id = ctx.get("topic_id")
            current_post_number = ctx.get("post_number")

            if topic_id and current_post_number and topic_id in discourse_topics_map:
                topic_posts = discourse_topics_map[topic_id]
                current_post_index = -1
                for i, p in enumerate(topic_posts):
                    if p.get("post_number") == current_post_number:
                        current_post_index = i
                        break

                if current_post_index != -1:
                    # Add next 1 or 2 posts if they exist
                    for i in range(1, 3):  # For next post, and post after next
                        next_post_index = current_post_index + i
                        if next_post_index < len(topic_posts):
                            next_post_data = topic_posts[next_post_index]
                            # Check if this next_post_data is already part of the initially retrieved contexts
                            # or already added to final_contexts_for_llm to avoid too much redundancy.
                            # For simplicity now, just add if not already processed by URL.
                            if next_post_data["url"] not in processed_urls:
                                final_contexts_for_llm.append(next_post_data)
                                processed_urls.add(next_post_data["url"])
                                print(
                                    f"  Added reply context: {next_post_data.get('topic_title', 'N/A')[:30]}... (Post {next_post_data['post_number']})"
                                )
                        else:
                            break  # No more posts in this topic
    # Now, final_contexts_for_llm might have more than top_n items.
    # You might want to limit the total number of contexts sent to the LLM, e.g., to 5 or 6.
    # Or, ensure your prompt can handle a variable number of contexts.
    # For now, let's assume the LLM prompt can handle up to ~6 contexts effectively.
    # The LLM prompt already iterates through `contexts`, so it's fine.

    if not final_contexts_for_llm:
        llm_answer = "I could not find relevant information in my documents to answer your question."
        derived_links = []
    else:
        print(
            f"Total contexts (including replies) for LLM: {len(final_contexts_for_llm)}"
        )
        llm_answer = await generate_llm_answer(
            request.question, final_contexts_for_llm
        )  # Pass the augmented list
        derived_links = []
        for ctx in final_contexts_for_llm:
            url = str(ctx.get("url", "#"))
            title = str(ctx.get("title", "Relevant Document"))
            # Link canonicalization
            if (
                url.startswith("https://tds.s-anand.net#") and "/../" in url
            ):  # More specific to the known URL structure
                parts = url.split("#", 1)  # Split only on the first #
                base = parts[0]
                hash_path = parts[1] if len(parts) > 1 else ""
                # Replace /../ which implies going up one segment from root of hash path
                # e.g., #/2025-01/../docker becomes #/docker (incorrect for this site)
                # e.g., #/../docker becomes #/docker (correct for this site if #/ is root)
                # The links are like "#/../docker", meaning relative to the root of the hash path.
                # So, "#/../<name>" should become "#/<name>"
                if hash_path.startswith("/../"):
                    hash_path = hash_path.replace(
                        "/../", "/", 1
                    )  # Replace only the first instance at the start
                url = base + "#" + hash_path
            derived_links.append(Link(url=url, text=title[:100]))

    if "could not find" in llm_answer.lower() or "no information" in llm_answer.lower():
        pass

    return AnswerResponse(answer=llm_answer, links=derived_links)
