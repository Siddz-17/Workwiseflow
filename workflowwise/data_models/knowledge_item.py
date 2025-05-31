from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime

@dataclass
class KnowledgeItem:
    id: str
    source: str # e.g., 'confluence', 'slack', 'jira'
    type: str # e.g., 'document', 'message', 'ticket'
    content: str
    embedding: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class UserQuery:
    query_text: str
    user_id: str
    session_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict) # To store conversation history or other contextual info
