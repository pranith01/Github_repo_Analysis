import streamlit as st
import requests
import openai
import time
import configparser
import base64
from cachetools import TTLCache

# Read the API key from the config file
config = configparser.ConfigParser()
config.read("config.ini")
OPENAI_API_KEY = config.get("openai", "api_key")

# Function to get user repositories
def get_user_repositories(username):
    url = f"https://api.github.com/users/{username}/repos"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for non-200 responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching repositories for {username}: {e}")
        return None

# Function to preprocess code before passing it into GPT
def preprocess_code(repo_name, code_url):
    try:
        # Fetch the raw code content
        response = requests.get(code_url)
        response.raise_for_status()  # Raise an exception for non-200 responses
        code_content = response.text

        # Base64 encode the content to avoid token limit issues
        encoded_code_content = base64.b64encode(code_content.encode()).decode()

        return f"This is the repository: {repo_name}\nCode: {encoded_code_content}\n\n"
    except requests.exceptions.RequestException as e:
        print(f"Error fetching code for {repo_name}: {e}")
        return None

# Function to evaluate technical complexity using GPT
def evaluate_complexity(prompt, openai_api_key):
    # Check if the result is already in the cache
    if prompt in complexity_cache:
        return complexity_cache[prompt]

    try:
        # Set up OpenAI API
        openai.api_key = openai_api_key

        # Call GPT to get evaluation
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            temperature=0.7,
            max_tokens=500,  # Increase max_tokens for longer analysis
            n=1,
            stop=None
        )

        complexity = response['choices'][0]['text']

        # Cache the result
        complexity_cache[prompt] = complexity

        return complexity
    except Exception as e:
        print(f"Error during GPT evaluation: {e}")
        return None

def main():
    st.title("GitHub Repo Complexity Analysis")
    st.write("Enter the GitHub user URL/ID to fetch repositories:")

    github_url = st.text_input("GitHub User URL/ID:")
    if not github_url:
        st.stop()

    if st.button("Analyze"):
        username = github_url.split("/")[-1]
        st.write(f"Fetching repositories for user: {username}...")
        repositories = get_user_repositories(username)
        if repositories is None:
            st.write(f"Failed to fetch repositories for user: {username}")
        else:
            st.write(f"Found {len(repositories)} repositories for the given username:")
            max_complexity_repo = None
            max_complexity_value = -1
            for repo in repositories:
                name = repo['name']
                description = repo['description']
                language = repo['language']

                # Skip repositories with missing description or language
                if not description or not language:
                    continue

                # Fetch the repository contents
                contents_url = repo['contents_url'].replace("{+path}", "")
                response = requests.get(contents_url)
                if response.status_code == 200:
                    contents = response.json()
                else:
                    continue

                # Preprocess and analyze code files in the repository
                prompt = f"This is the repository: {name}\nDescription: {description}\nLanguage: {language}\n\n"
                for content in contents:
                    if content['type'] == "file" and content['name'].endswith((".py", ".ipynb", ".r", ".cpp")):
                        code_url = content['download_url']
                        code_prompt = preprocess_code(content['name'], code_url)
                        if code_prompt is not None:
                            prompt += code_prompt

                # Sleep to avoid rate limiting issues
                time.sleep(1)

                complexity_result = evaluate_complexity(prompt, OPENAI_API_KEY)
                if complexity_result is not None:
                    complexity = len(complexity_result)
                    if complexity > max_complexity_value:
                        max_complexity_value = complexity
                        max_complexity_repo = repo

            if max_complexity_repo:
                st.write("Most Complex Repository:")
                repo_name = max_complexity_repo['name']
                repo_description = max_complexity_repo['description']
                repo_language = max_complexity_repo['language']
                st.write(f"\nName: {repo_name}\nDescription: {repo_description}\nLanguage: {repo_language}")

                st.write("Technical Complexity Analysis:")
                st.write(complexity_result)

                repo_link = f"https://github.com/{username}/{repo_name}"
                st.markdown(f"Link to the most complex repository: [{repo_name}]({repo_link})")
if __name__ == "__main__":
    # Dictionary to store cached complexity results
    complexity_cache = TTLCache(maxsize=100, ttl=3600)  # Cache up to 100 items for 1 hour
    main()
