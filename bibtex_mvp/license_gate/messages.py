from . import error_codes as codes

ERROR_MESSAGES_ZH = {
    codes.LICENSE_NOT_FOUND: "未找到本地许可证",
    codes.INVALID_JSON: "许可证 JSON 格式无效",
    codes.CORRUPTED_LICENSE: "许可证结构损坏或字段缺失",
    codes.UNSUPPORTED_VERSION: "许可证版本不受支持",
    codes.INVALID_SIGNATURE: "许可证签名无效",
    codes.EXPIRED: "许可证已过期",
    codes.DEVICE_ID_UNAVAILABLE: "无法获取本机设备标识",
    codes.DEVICE_MISMATCH: "许可证与当前设备不匹配",
}

