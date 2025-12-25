from datetime import datetime
from dateutil.parser import parse

def compute_priority(task):
    score = 0

    if task["blocks_others"]:
        score += 3
    if task["external_dependency"]:
        score += 2
    if task["stakeholder"] in ["CEO", "Chairman"]:
        score += 2
    if task["due_by"]:
        days = (parse(task["due_by"]) - datetime.now()).days
        if days <= 3:
            score += 2
    if task["delegatable"]:
        score -= 1

    return score

