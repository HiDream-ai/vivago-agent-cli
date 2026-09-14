"use strict";

const PROFILE = Object.freeze({
  name: "domestic-prod",
  skillName: "gouda-agent",
  skillVersion: "1.0.1",
  apiBaseURL: "https://goudaai.com",
  webBaseURL: "https://goudaai.com",
  loginURL: "https://goudaai.com/login",
  paymentURLs: Object.freeze({
    credits:
      "https://market.volcengine.com/goods/detail?goodsId=wysf9000287&detailFrom=2",
    membership:
      "https://market.volcengine.com/goods/detail?goodsId=wysf9000286&detailFrom=2",
  }),
  paymentReturnURL: "https://goudaai.com/home",
  refreshPath: "/prod-api/user/apikey2token",
  ossCredentialPath: "/prod-api/user/oss_key",
  projectVersion: "v3",
  imagePrefix: "https://storage-cdn.hidreamai.com/image/",
  mediaPrefix: "https://media-cdn.hidreamai.com/",
  aliyunRegion: "oss-cn-beijing",
});

module.exports = { PROFILE };
