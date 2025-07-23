def load_properties(filepath: str) -> dict:
    props = {}
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith(";"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    props[key.strip()] = value.strip()
    return props

#  import 될 때 자동 로딩
_properties = load_properties("/home/ec2-user/blog-tistory-comment-bot/config.properties")

#  모든 key를 변수로 자동 등록
for key, value in _properties.items():
    globals()[key] = value
