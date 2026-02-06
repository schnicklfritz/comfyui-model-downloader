#!/usr/bin/env python3
"""
Golemite Mission System - The brain of the clay.
Dynamically loads and runs formation plugins.
"""
import importlib
import pkgutil
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio

class MissionControl:
    """Discovers and manages formation plugins."""
    
    def __init__(self, formations_dir: Path):
        self.formations_dir = formations_dir
        self.formations: Dict[str, Any] = {}
        self._load_formations()
    
    def _load_formations(self):
        """Dynamically load all formation modules."""
        # Add formations directory to Python path
        if str(self.formations_dir) not in sys.path:
            sys.path.insert(0, str(self.formations_dir))
        
        # Import the formations package
        try:
            import formations
        except ImportError:
            print(f"⚠️ No formations package found in {self.formations_dir}")
            return
        
        # Discover all formation modules
        for _, module_name, is_pkg in pkgutil.iter_modules(
            formations.__path__, 
            formations.__name__ + '.'
        ):
            if not is_pkg and not module_name.endswith('.base'):
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, 'FORMATION_CLASS'):
                        formation_class = module.FORMATION_CLASS
                        formation = formation_class()
                        self.formations[formation.name] = formation
                        print(f"✅ Loaded formation: {formation.name}")
                except Exception as e:
                    print(f"⚠️ Failed to load {module_name}: {e}")
    
    def get_formation(self, name: str):
        """Get a formation by name or URL pattern."""
        # Direct name lookup
        if name in self.formations:
            return self.formations[name]
        
        # URL pattern matching
        for formation in self.formations.values():
            if formation.matches_url(name):
                return formation
        
        return None
    
    async def execute(self, formation_name: str, target_url: str, **kwargs):
        """Execute a mission with the specified formation."""
        formation = self.get_formation(formation_name)
        if not formation:
            raise ValueError(f"No formation found for: {formation_name}")
        
        print(f"🎯 Mission started with {formation.name}")
        print(f"   Target: {target_url}")
        
        try:
            result = await formation.execute(target_url, **kwargs)
            print(f"✅ Mission completed successfully")
            return result
        except Exception as e:
            print(f"❌ Mission failed: {e}")
            raise

# Global mission control instance
mission_control: Optional[MissionControl] = None

def get_mission_control(formations_dir: Path = None):
    """Get or create the global mission control instance."""
    global mission_control
    if mission_control is None:
        if formations_dir is None:
            formations_dir = Path(__file__).parent / "formations"
        mission_control = MissionControl(formations_dir)
    return mission_control
