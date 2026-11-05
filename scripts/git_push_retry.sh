#!/usr/bin/env bash
# Rebase e push com repeticao para evitar falhas de concorrencia entre workflows.
set -euo pipefail

branch="${1:-${GITHUB_REF_NAME:-main}}"
max_attempts=8

for ((attempt=1; attempt<=max_attempts; attempt++)); do
  echo "Publicacao no GitHub: tentativa ${attempt}/${max_attempts} (branch ${branch})."

  # Atualiza a referencia remota: outros workflows podem ter publicado commits.
  git fetch origin "${branch}"
  if ! git rebase "origin/${branch}"; then
    git rebase --abort || true
    echo "::error::Rebase com conflito real. Publicacao interrompida para proteger os dados."
    exit 1
  fi

  if git push origin "HEAD:${branch}"; then
    echo "Publicacao concluida."
    exit 0
  fi

  if ((attempt < max_attempts)); then
    delay=$((attempt * 3))
    echo "::warning::Push recusado/transitorio. Nova tentativa em ${delay}s."
    sleep "${delay}"
  fi
done

echo "::error::Nao foi possivel publicar no GitHub apos ${max_attempts} tentativas."
exit 1
