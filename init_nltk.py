import nltk
import os

nltk_data_path = os.path.expanduser('~/nltk_data')
os.makedirs(nltk_data_path, exist_ok=True)

try:
    nltk.data.find('tokenizers/punkt')
    print("NLTK punkt tokenizer already downloaded")
except LookupError:
    print("Downloading NLTK punkt tokenizer...")
    nltk.download('punkt', quiet=True)
    print("NLTK punkt tokenizer downloaded successfully")

try:
    nltk.data.find('tokenizers/punkt_tab')
    print("NLTK punkt_tab tokenizer already downloaded")
except LookupError:
    try:
        print("Downloading NLTK punkt_tab tokenizer...")
        nltk.download('punkt_tab', quiet=True)
        print("NLTK punkt_tab tokenizer downloaded successfully")
    except:
        print("punkt_tab not available, using punkt instead")
