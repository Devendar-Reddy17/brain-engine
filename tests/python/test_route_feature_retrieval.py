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

AUTH_CONTROLLER = """\
package com.example.security.controller;

import com.example.security.dto.AuthResponse;
import com.example.security.dto.MfaVerifyRequest;
import com.example.security.service.AuthService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {
    private final AuthService authService;

    @PostMapping("/login")
    public AuthResponse login(@RequestBody LoginRequest request) {
        return authService.login(request);
    }

    @PostMapping("/verify-mfa")
    public AuthResponse verifyMfa(@RequestBody MfaVerifyRequest request) {
        return authService.verifyMfa(request);
    }
}
"""

MFA_CONTROLLER = """\
package com.example.security.controller;

import com.example.security.dto.MfaSetupResponse;
import com.example.security.dto.MfaVerifyRequest;
import com.example.security.service.MfaService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/mfa")
@RequiredArgsConstructor
public class MfaController {
    private final MfaService mfaService;

    @PostMapping("/setup")
    public MfaSetupResponse setupMfa() {
        String secret = mfaService.generateSecret();
        return new MfaSetupResponse(secret, mfaService.generateQrCodeImageUri(secret));
    }

    @PostMapping("/verify-setup")
    public boolean verifySetup(@RequestBody MfaVerifyRequest request) {
        return mfaService.verifyCode("secret", request.getCode());
    }
}
"""

AUTH_SERVICE = """\
package com.example.security.service;

import com.example.security.dto.AuthResponse;
import com.example.security.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AuthService {
    private final JwtService jwtService;
    private final MfaService mfaService;

    public AuthResponse login(LoginRequest request) {
        User user = new User();
        if (user.isMfaEnabled()) {
            return AuthResponse.mfaRequired(jwtService.generateMfaToken(user));
        }
        return AuthResponse.success(jwtService.generateToken(user));
    }

    public AuthResponse verifyMfa(MfaVerifyRequest request) {
        User user = new User();
        if (!mfaService.verifyCode(user.getMfaSecret(), request.getCode())) {
            throw new RuntimeException("Invalid MFA code");
        }
        return AuthResponse.success(jwtService.generateToken(user));
    }
}
"""

MFA_SERVICE = """\
package com.example.security.service;

import dev.samstevens.totp.code.CodeVerifier;
import dev.samstevens.totp.qr.QrDataFactory;
import dev.samstevens.totp.secret.SecretGenerator;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class MfaService {
    private final SecretGenerator secretGenerator;
    private final QrDataFactory qrDataFactory;
    private final CodeVerifier codeVerifier;

    public String generateSecret() {
        return secretGenerator.generate();
    }

    public String generateQrCodeImageUri(String secret) {
        return qrDataFactory.newBuilder().secret(secret).build().getUri();
    }

    public boolean verifyCode(String secret, String code) {
        return codeVerifier.isValidCode(secret, code);
    }
}
"""

JWT_SERVICE = """\
package com.example.security.service;

import com.example.security.entity.User;
import org.springframework.stereotype.Service;

@Service
public class JwtService {
    public String generateToken(User user) {
        return "jwt";
    }

    public String generateMfaToken(User user) {
        return "mfa-jwt";
    }
}
"""

USER_ENTITY = """\
package com.example.security.entity;

import jakarta.persistence.Entity;

@Entity
public class User {
    private boolean mfaEnabled;
    private String mfaSecret;
}
"""

AUTH_RESPONSE = """\
package com.example.security.dto;

public class AuthResponse {
    private boolean mfaRequired;
    private String mfaToken;
    private boolean mfaEnabled;

    public static AuthResponse mfaRequired(String token) {
        return new AuthResponse();
    }

    public static AuthResponse success(String token) {
        return new AuthResponse();
    }
}
"""

MFA_SETUP_RESPONSE = """\
package com.example.security.dto;

public class MfaSetupResponse {
    private String secret;
    private String qrCodeImageUri;
}
"""

MFA_VERIFY_REQUEST = """\
package com.example.security.dto;

public class MfaVerifyRequest {
    private String code;
}
"""

LOGIN_PAGE = """\
export function LoginPage() {
  const mfaRequired = true;
  return <form>{mfaRequired ? <input aria-label="MFA code" /> : null}</form>;
}
"""

MFA_SETUP_PAGE = """\
export function MfaSetupPage() {
  return <section>Two-Factor Authentication QR code setup</section>;
}
"""

WORKFLOW_TWO = """\
package com.example.workflow;

public class FinalSubmitListener {
    public void twoStepWorkflow() {
    }
}
"""

SCORE_FACTOR = """\
package com.example.scoreengine;

public class ScoreFactor {
    private int factor;
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


def test_multifactor_intent_retrieves_flow_chunks_without_weak_fragment_noise(tmp_path: Path):
    _write(tmp_path / "backend/src/main/java/com/example/security/controller/AuthController.java", AUTH_CONTROLLER)
    _write(tmp_path / "backend/src/main/java/com/example/security/controller/MfaController.java", MFA_CONTROLLER)
    _write(tmp_path / "backend/src/main/java/com/example/security/service/AuthService.java", AUTH_SERVICE)
    _write(tmp_path / "backend/src/main/java/com/example/security/service/MfaService.java", MFA_SERVICE)
    _write(tmp_path / "backend/src/main/java/com/example/security/service/JwtService.java", JWT_SERVICE)
    _write(tmp_path / "backend/src/main/java/com/example/security/entity/User.java", USER_ENTITY)
    _write(tmp_path / "backend/src/main/java/com/example/security/dto/AuthResponse.java", AUTH_RESPONSE)
    _write(tmp_path / "backend/src/main/java/com/example/security/dto/MfaSetupResponse.java", MFA_SETUP_RESPONSE)
    _write(tmp_path / "backend/src/main/java/com/example/security/dto/MfaVerifyRequest.java", MFA_VERIFY_REQUEST)
    _write(tmp_path / "frontend/ui/src/pages/LoginPage.jsx", LOGIN_PAGE)
    _write(tmp_path / "frontend/ui/src/pages/MfaSetupPage.jsx", MFA_SETUP_PAGE)
    _write(tmp_path / "backend/src/main/java/com/example/workflow/FinalSubmitListener.java", WORKFLOW_TWO)
    _write(tmp_path / "backend/src/main/java/com/example/scoreengine/ScoreFactor.java", SCORE_FACTOR)

    config = default_config()
    db = Database(tmp_path)
    embedder = get_embedding_provider(config)
    Indexer(str(tmp_path), db, embedder, config).full_index()

    result = ContextRetriever(str(tmp_path), db, embedder, config).retrieve(
        "Does this codebase have multi-factor authentication or two-factor authentication for user login?"
    )

    files = [f.path for f in result.relevant_files]
    assert "backend/src/main/java/com/example/security/controller/AuthController.java" in files
    assert "backend/src/main/java/com/example/security/controller/MfaController.java" in files
    assert "backend/src/main/java/com/example/security/service/AuthService.java" in files
    assert "backend/src/main/java/com/example/security/service/MfaService.java" in files
    assert "backend/src/main/java/com/example/security/service/JwtService.java" in files
    assert "backend/src/main/java/com/example/security/entity/User.java" in files
    assert "backend/src/main/java/com/example/security/dto/AuthResponse.java" in files
    assert "backend/src/main/java/com/example/security/dto/MfaSetupResponse.java" in files
    assert "backend/src/main/java/com/example/security/dto/MfaVerifyRequest.java" in files
    assert "frontend/ui/src/pages/LoginPage.jsx" in files
    assert "frontend/ui/src/pages/MfaSetupPage.jsx" in files
    assert "backend/src/main/java/com/example/workflow/FinalSubmitListener.java" not in files[:12]
    assert "backend/src/main/java/com/example/scoreengine/ScoreFactor.java" not in files[:12]
