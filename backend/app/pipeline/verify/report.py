from dataclasses import dataclass, field


@dataclass
class Finding:
    path: str
    message: str
    layer: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def as_text(self) -> str:
        if not self.findings:
            return "valid"
        return "\n".join(f"- {item.layer} {item.path}: {item.message}" for item in self.findings)
