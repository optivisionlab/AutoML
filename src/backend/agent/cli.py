"""
Chạy agent từ dòng lệnh.

    cd src/backend

    # Provider mặc định lấy từ LLM_PROVIDER trong .env
    python -m agent.cli "Đăng ký tài khoản mới cho tôi rồi thử đăng nhập"

    # Chỉ định provider ngay trên dòng lệnh
    python -m agent.cli --provider google "..."

Muốn dùng model của Anthropic thì đi qua OpenRouter:
    LLM_PROVIDER=openrouter LLM_MODEL=anthropic/claude-sonnet-4.6
"""

# Standard libraries
import argparse

# Local modules
from agent import providers


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent thao tác API xác thực HAutoML")
    parser.add_argument("prompt", nargs="+", help="Yêu cầu bằng ngôn ngữ tự nhiên")
    parser.add_argument(
        "--provider",
        default=None,
        help=(
            f"{' | '.join(providers.SUPPORTED)}. "
            "Mặc định: biến LLM_PROVIDER, hoặc openrouter"
        ),
    )
    parser.add_argument("--model", default=None, help="Slug model, mặc định theo provider")
    parser.add_argument("--base-url", default=None, help="URL backend, mặc định localhost:9996")
    parser.add_argument("--quiet", action="store_true", help="Không in các bước gọi tool")
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    verbose = not args.quiet

    from agent.agent_openai import run_agent

    answer = run_agent(
        prompt=prompt,
        base_url=args.base_url,
        provider=args.provider,
        model=args.model,
        verbose=verbose,
    )

    print("\n=== Kết quả ===")
    print(answer)


if __name__ == "__main__":
    main()
