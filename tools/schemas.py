from tools.edit import EDIT_TOOLS
from tools.git import GIT_TOOLS
from tools.index import INDEX_TOOLS
from tools.read import READ_TOOLS
from tools.run import RUN_TOOLS
from tools.search import SEARCH_TOOLS
from tools.tasks import TASK_TOOLS

ALL_TOOLS = (
    READ_TOOLS
    + EDIT_TOOLS
    + SEARCH_TOOLS
    + RUN_TOOLS
    + TASK_TOOLS
    + INDEX_TOOLS
    + GIT_TOOLS
)
