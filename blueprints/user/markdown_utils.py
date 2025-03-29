import markdown2
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter
import re
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Pre-compile the regular expression for code blocks
CODE_BLOCK_RE = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)

def highlight_code(match):
    """
    Process each code block match and apply syntax highlighting with Pygments
    """
    lang = match.group(1) or 'text'
    code = match.group(2)
    
    try:
        lexer = get_lexer_by_name(lang, stripall=True)
    except Exception:
        logger.warning(f"Lexer for language '{lang}' not found, using text lexer")
        lexer = TextLexer()
    
    formatter = HtmlFormatter(linenos=False, cssclass="code-highlight")
    highlighted = highlight(code, lexer, formatter)
    
    # Wrap with proper pre and code tags
    return f'<pre class="hljs"><code class="language-{lang}">{highlighted}</code></pre>'

def render_markdown_with_highlighting(text):
    """
    Pre-process code blocks with Pygments highlighting and then render the rest as markdown
    """
    if not text:
        return ""
    
    try:
        # First, handle code blocks with syntax highlighting
        processed_text = CODE_BLOCK_RE.sub(highlight_code, text)
        
        # Use markdown2 to render the processed text
        extras = [
            "fenced-code-blocks",
            "tables",
            "code-friendly"
        ]
        html = markdown2.markdown(processed_text, extras=extras)
        return html
    except Exception as e:
        logger.error(f"Error rendering markdown: {str(e)}")
        return text 