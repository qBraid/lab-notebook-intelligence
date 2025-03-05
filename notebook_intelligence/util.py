# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

def extract_llm_generated_code(code: str) -> str:
        if code.endswith("```"):
            code = code[:-3]

        lines = code.split("\n")
        if len(lines) < 2:
            return code

        num_lines = len(lines)
        start_line = -1
        end_line = num_lines

        for i in range(num_lines):
            if start_line == -1:
                if lines[i].lstrip().startswith("```"):
                    start_line = i
                    continue
            else:
                if lines[i].lstrip().startswith("```"):
                    end_line = i
                    break

        if start_line != -1:
            lines = lines[start_line+1:end_line]

        return "\n".join(lines)
