"""Configuration management for Aquawar games."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    model: str
    temperature: float = 0.7
    reasoning: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "reasoning": self.reasoning
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelConfig':
        return cls(
            model=data["model"],
            temperature=data.get("temperature", 0.7),
            reasoning=data.get("reasoning", False)
        )


@dataclass
class PlayerConfig:
    """Configuration for a single player."""
    type: str
    models: List[ModelConfig]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "models": [model.to_dict() for model in self.models]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerConfig':
        return cls(
            type=data["type"],
            models=[ModelConfig.from_dict(model_data) for model_data in data["models"]]
        )


@dataclass
class GameConfig:
    """Configuration for a complete game."""
    player_1: PlayerConfig
    player_2: PlayerConfig
    max_tries: int = 3  # Maximum retry attempts for failed moves
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_1": self.player_1.to_dict(),
            "player_2": self.player_2.to_dict(),
            "max_tries": self.max_tries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameConfig':
        return cls(
            player_1=PlayerConfig.from_dict(data["player_1"]),
            player_2=PlayerConfig.from_dict(data["player_2"]),
            max_tries=data.get("max_tries", 3)
        )
    
    def save_to_file(self, filepath: Path) -> None:
        """Save configuration to a JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: Path) -> 'GameConfig':
        """Load configuration from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)


def create_default_ollama_config(model: str = "llama3.2:3b", temperature: float = 0.7, max_tries: int = 3) -> GameConfig:
    """Create a default configuration for Ollama AI vs AI games."""
    model_config = ModelConfig(model=model, temperature=temperature, reasoning=False)
    
    player_1 = PlayerConfig(type="OllamaPlayer", models=[model_config])
    player_2 = PlayerConfig(type="OllamaPlayer", models=[model_config])
    
    return GameConfig(player_1=player_1, player_2=player_2, max_tries=max_tries)


def create_mixed_model_config(
    model1: str = "llama3.2:3b", 
    model2: str = "gpt-oss:20b",
    temperature: float = 0.7,
    max_tries: int = 3
) -> GameConfig:
    """Create a configuration for testing different models against each other."""
    model_config_1 = ModelConfig(model=model1, temperature=temperature, reasoning=False)
    model_config_2 = ModelConfig(model=model2, temperature=temperature, reasoning=False)
    
    player_1 = PlayerConfig(type="OllamaPlayer", models=[model_config_1])
    player_2 = PlayerConfig(type="OllamaPlayer", models=[model_config_2])
    
    return GameConfig(player_1=player_1, player_2=player_2, max_tries=max_tries)