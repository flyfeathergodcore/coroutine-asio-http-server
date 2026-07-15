from enum import Enum
from dataclasses import dataclass
from typing import Dict, Set, Optional

# 1. 元数据定义（不变）
@dataclass(frozen=True)
class StateMetadata:
    timeout_seconds: int = 30
    max_retries: int = 3
    description: str = ""
    transition_context:str = ""
    requires_user_input: bool = False
    is_terminal: bool = False  # 新增：是否终止状态

# 2. 正确写法：Enum 的值用字符串，元数据映射到外部
class AgentState(Enum):
    INIT = "init"
    OBSERVING= "observing"
    DETAIL = "detail"
    ASKING = "asking"
    DONE = "done"
    FAILED = "failed"
    
    # 元数据映射表（类属性）
    _METADATA: Dict["AgentState", StateMetadata] = {
        INIT: StateMetadata(
            timeout_seconds=15,
            description="初始化阶段",
            max_retries=2
        ),
        DETAIL: StateMetadata(
            timeout_seconds=5,
            max_retries=2,
            description="探索细节部分",
        ),
        ASKING: StateMetadata(
            timeout_seconds=30,
            max_retries=3,
            description="询问更多信息"
        ),
        OBSERVING: StateMetadata(
            timeout_seconds=10,
            max_retries=1,
            description="结果观察阶段"
        ),
        DONE: StateMetadata(
            timeout_seconds=0,
            description="完成状态",
            is_terminal=True
        ),
        FAILED: StateMetadata(
            timeout_seconds=0,
            description="失败状态",
            is_terminal=True
        ),
    }

    # ===== 转移规则表（核心） =====
    _TRANSITIONS: Dict["AgentState", Set["AgentState"]] = {
        INIT: {DETAIL, ASKING,OBSERVING},
        DETAIL: {ASKING,OBSERVING,FAILED},
        ASKING: {OBSERVING, FAILED},
        OBSERVING: {DETAIL, DONE, FAILED},
        DONE: set(),        # 终止状态，不能再转
        FAILED: set(),      # 终止状态，不能再转
    }
    
    # ===== 辅助属性 =====
    @property
    def metadata(self) -> StateMetadata:
        return self._METADATA[self]
    
    @property
    def timeout(self) -> int:
        return self.metadata.timeout_seconds
    
    @property
    def max_retries(self) -> int:
        return self.metadata.max_retries
    
    @property
    def description(self) -> str:
        return self.metadata.description
    
    @property
    def is_terminal(self) -> bool:
        return self.metadata.is_terminal
    
    @property
    def is_active(self) -> bool:
        return not self.is_terminal
    
     # ===== 转移校验方法 =====
    @classmethod
    def can_transition(cls, from_state: "AgentState", to_state: "AgentState") -> bool:
        """检查是否能从 from_state 转移到 to_state"""
        # 如果任一状态为 None，返回 False
        if from_state is None or to_state is None:
            return False
        
        # 从终止状态不能转移
        if from_state.is_terminal:
            return False
        
        # 检查转移表
        allowed = cls._TRANSITIONS.get(from_state, set())
        return to_state in allowed
    
    @classmethod
    def get_allowed_transitions(cls, from_state: "AgentState") -> Set["AgentState"]:
        """获取从某状态可以转移到的所有状态"""
        if from_state is None or from_state.is_terminal:
            return set()
        return cls._TRANSITIONS.get(from_state, set())
    
    # ===== 便捷方法：直接在当前实例上调用 =====
    def can_go_to(self, target: "AgentState") -> bool:
        """实例方法：self 是否能转移到 target"""
        return self.can_transition(self, target)
    
    def allowed_targets(self) -> Set["AgentState"]:
        """实例方法：获取当前状态允许转移的目标列表"""
        return self.get_allowed_transitions(self)
    
    def set_transition_context(self,context:str)->bool:
        if context:
            self.metadata.transition_context = context
            return True
        return False