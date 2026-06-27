from pathlib import Path

from brain.config.default_config import default_config
from brain.core.db.database import Database
from brain.core.embeddings.embedding_provider import get_embedding_provider
from brain.core.indexing.indexer import Indexer
from brain.core.retrieval.context_retriever import ContextRetriever


CONTROLLER = """\
package com.example.verification.controller;

import com.example.verification.dto.VerificationDto;
import com.example.verification.service.VerificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/verifications")
@RequiredArgsConstructor
public class VerificationController {
    private final VerificationService verificationService;

    @GetMapping("/{id}")
    public ResponseEntity<VerificationDto> getVerification(@PathVariable Long id) {
        return ResponseEntity.ok(verificationService.getVerification(id));
    }

    @GetMapping("/user/{userId}")
    public ResponseEntity<VerificationDto> getVerificationsByUser(@PathVariable Long userId) {
        return ResponseEntity.ok(verificationService.getVerificationsByUser(userId));
    }
}
"""

SERVICE = """\
package com.example.verification.service;

import com.example.verification.dto.VerificationDto;
import org.springframework.stereotype.Service;

@Service
public class VerificationService {
    public VerificationDto getVerification(Long id) {
        return null;
    }
}
"""

DTO = """\
package com.example.verification.dto;

public class VerificationDto {
    private Long id;
}
"""

REPOSITORY = """\
package com.example.verification.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface VerificationRequestRepository extends JpaRepository<VerificationRequest, Long> {
}
"""

UNRELATED_DTO = """\
package com.example.other.dto;

public class ConsentDto {
    private Long id;
}
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_exact_route_retrieval_includes_same_feature_service_dto_and_repository(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/example/verification/controller/VerificationController.java", CONTROLLER)
    _write(tmp_path / "src/main/java/com/example/verification/service/VerificationService.java", SERVICE)
    _write(tmp_path / "src/main/java/com/example/verification/dto/VerificationDto.java", DTO)
    _write(tmp_path / "src/main/java/com/example/verification/repository/VerificationRequestRepository.java", REPOSITORY)
    _write(tmp_path / "src/main/java/com/example/other/dto/ConsentDto.java", UNRELATED_DTO)

    config = default_config()
    db = Database(tmp_path)
    embedder = get_embedding_provider(config)
    Indexer(str(tmp_path), db, embedder, config).full_index()

    result = ContextRetriever(str(tmp_path), db, embedder, config).retrieve(
        "Find the controller method handling GET /api/verifications/{id}, "
        "its service implementation, the DTO it returns, and the JPA repository backing it"
    )

    files = [f.path for f in result.relevant_files]
    assert "src/main/java/com/example/verification/controller/VerificationController.java" in files
    assert "src/main/java/com/example/verification/service/VerificationService.java" in files
    assert "src/main/java/com/example/verification/dto/VerificationDto.java" in files
    assert "src/main/java/com/example/verification/repository/VerificationRequestRepository.java" in files
    assert "src/main/java/com/example/other/dto/ConsentDto.java" not in files[:8]

    first_symbols = [s.name for s in result.target_symbols[:6]]
    assert "getVerification" in first_symbols


def test_exact_route_retrieval_works_for_express_feature_layout(tmp_path: Path):
    _write(
        tmp_path / "src/features/users/routes/users.routes.ts",
        """\
import { Router } from 'express';
import { getUser } from '../services/user.service';
const router = Router();
router.get('/api/users/:id', getUser);
""",
    )
    _write(
        tmp_path / "src/features/users/services/user.service.ts",
        """\
export function getUser(req, res) {
  return res.json({});
}
""",
    )
    _write(
        tmp_path / "src/features/users/components/UserCard.tsx",
        """\
export function UserCard({ user }) {
  return <div>{user.name}</div>;
}
""",
    )

    config = default_config()
    db = Database(tmp_path)
    embedder = get_embedding_provider(config)
    Indexer(str(tmp_path), db, embedder, config).full_index()

    result = ContextRetriever(str(tmp_path), db, embedder, config).retrieve(
        "Find the handler for GET /api/users/{id} and the related service and component"
    )

    files = [f.path for f in result.relevant_files]
    assert "src/features/users/routes/users.routes.ts" in files
    assert "src/features/users/services/user.service.ts" in files
    assert "src/features/users/components/UserCard.tsx" in files
