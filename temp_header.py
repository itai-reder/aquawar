"""Ollama client integration for Aquawar using Langchain.

This module provides Ollama AI integration for autonomous gameplay using Langchain's
tool calling capabilities.
"""

from __future__ import annotations

import json
from typing import List, Optional, Any, Dict, Union
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from pydantic import BaseModel, Field

from core.game import Game, FISH_NAMES
from core.persistent_game import PersistentGameManager


@dataclass
