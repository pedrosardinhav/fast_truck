"""Consulta opcional de dados públicos empresariais, sem salvar o formulário."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from common import ApiError


MAX_BYTES = 1_048_576


def lookup_cnpj(cnpj: str) -> dict:
    request = Request(
        f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
        headers={"Accept": "application/json", "User-Agent": "FasTruck/1.0"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ApiError(502, "Resposta externa excedeu o tamanho permitido. Preencha os dados manualmente.")
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("razao_social"), str):
            raise ValueError("Resposta inesperada")
    except HTTPError as exc:
        if exc.code == 404:
            raise ApiError(404, "Empresa não encontrada na consulta. O cadastro manual continua disponível.") from None
        if exc.code == 429 or exc.code >= 500:
            raise ApiError(503, "Consulta temporariamente indisponível. Preencha manualmente ou tente mais tarde.") from None
        raise ApiError(502, "O provedor não conseguiu concluir a consulta. Preencha os dados manualmente.") from None
    except (TimeoutError, socket.timeout):
        raise ApiError(504, "A consulta excedeu 5 segundos. O cadastro manual continua disponível.") from None
    except URLError as exc:
        status = 504 if isinstance(exc.reason, (TimeoutError, socket.timeout)) else 503
        raise ApiError(status, "Não foi possível acessar a consulta CNPJ. Preencha os dados manualmente.") from None
    except (ValueError, UnicodeDecodeError, OSError):
        raise ApiError(502, "Resposta externa inválida. O cadastro manual continua disponível.") from None

    def field(name: str, limit=254):
        value = data.get(name)
        return str(value).strip()[:limit] if isinstance(value, (str, int)) else ""

    return {
        "cnpj": cnpj,
        "legal_name": field("razao_social", 160), "trade_name": field("nome_fantasia", 160),
        "phone": field("ddd_telefone_1", 30), "email": field("email"),
        "postal_code": field("cep", 12), "street": field("logradouro", 160),
        "number": field("numero", 20), "complement": field("complemento", 100),
        "district": field("bairro", 100), "city": field("municipio", 100), "state": field("uf", 2),
        "lookup_status": field("descricao_situacao_cadastral", 120),
    }
