/** Static geographic landmarks rendered on the map as a context layer.
 *
 *  This dataset is the single source of truth for permanent reference
 *  points (central banks, strategic waterways, commodity hubs). It is
 *  intentionally hand-curated rather than backend-driven — landmark
 *  data doesn't change with event flow and lives close to the map UI
 *  that consumes it.
 *
 *  Each entry carries a `relevance` shape (countries / asset_ids /
 *  keywords) consumed by `landmarkRelevance.ts` to surface
 *  events-in-window that touch this landmark on hover.
 */

export type LandmarkCategory =
  | "central-bank"
  | "strategic-waterway"
  | "commodity-hub";

export interface Landmark {
  id: string;
  name_zh: string;
  name_en: string;
  lat: number;
  lng: number;
  category: LandmarkCategory;
  /** Free-text label only shown for commodity-hub (e.g. "Copper", "LNG"). */
  detail?: string;
  /** OR-logic event matchers. */
  countries?: string[];
  asset_ids?: string[];
  keywords?: string[];
}

export const LANDMARKS: Landmark[] = [
  // ===== Central banks (12) =====
  {
    id: "cb-fed", name_zh: "美联储", name_en: "Federal Reserve",
    lat: 38.8920, lng: -77.0457, category: "central-bank",
    countries: ["US"], keywords: ["Fed", "FOMC", "美联储", "Powell"],
  },
  {
    id: "cb-ecb", name_zh: "欧洲央行", name_en: "European Central Bank",
    lat: 50.1093, lng: 8.7026, category: "central-bank",
    countries: ["DE"], keywords: ["ECB", "Lagarde", "欧央行", "欧元区"],
  },
  {
    id: "cb-boj", name_zh: "日本央行", name_en: "Bank of Japan",
    lat: 35.6864, lng: 139.7714, category: "central-bank",
    countries: ["JP"], keywords: ["BoJ", "日银", "日央行", "Ueda"],
  },
  {
    id: "cb-boe", name_zh: "英国央行", name_en: "Bank of England",
    lat: 51.5142, lng: -0.0882, category: "central-bank",
    countries: ["GB"], keywords: ["BoE", "Bailey", "英央行"],
  },
  {
    id: "cb-pboc", name_zh: "中国人民银行", name_en: "People's Bank of China",
    lat: 39.9137, lng: 116.3675, category: "central-bank",
    countries: ["CN"], keywords: ["PBoC", "人民银行", "央行", "LPR", "潘功胜"],
  },
  {
    id: "cb-snb", name_zh: "瑞士国家银行", name_en: "Swiss National Bank",
    lat: 46.9479, lng: 7.4474, category: "central-bank",
    countries: ["CH"], keywords: ["SNB", "瑞士央行"],
  },
  {
    id: "cb-rba", name_zh: "澳大利亚联储", name_en: "Reserve Bank of Australia",
    lat: -33.8674, lng: 151.2087, category: "central-bank",
    countries: ["AU"], keywords: ["RBA", "澳联储"],
  },
  {
    id: "cb-boc", name_zh: "加拿大央行", name_en: "Bank of Canada",
    lat: 45.4204, lng: -75.7036, category: "central-bank",
    countries: ["CA"], keywords: ["Bank of Canada", "加拿大央行"],
  },
  {
    id: "cb-rbi", name_zh: "印度储备银行", name_en: "Reserve Bank of India",
    lat: 18.9320, lng: 72.8347, category: "central-bank",
    countries: ["IN"], keywords: ["RBI", "印度央行"],
  },
  {
    id: "cb-bcb", name_zh: "巴西央行", name_en: "Banco Central do Brasil",
    lat: -15.7913, lng: -47.8835, category: "central-bank",
    countries: ["BR"], keywords: ["BCB", "Banco Central", "巴西央行"],
  },
  {
    id: "cb-banxico", name_zh: "墨西哥央行", name_en: "Banco de México",
    lat: 19.4326, lng: -99.1374, category: "central-bank",
    countries: ["MX"], keywords: ["Banxico", "墨西哥央行"],
  },
  {
    id: "cb-cbr", name_zh: "俄罗斯央行", name_en: "Bank of Russia",
    lat: 55.7611, lng: 37.6219, category: "central-bank",
    countries: ["RU"], keywords: ["CBR", "俄罗斯央行", "Nabiullina"],
  },

  // ===== Strategic waterways (15) =====
  {
    id: "ww-hormuz", name_zh: "霍尔木兹海峡", name_en: "Strait of Hormuz",
    lat: 26.5, lng: 56.3, category: "strategic-waterway",
    keywords: ["Hormuz", "霍尔木兹", "Iran oil", "波斯湾"],
  },
  {
    id: "ww-malacca", name_zh: "马六甲海峡", name_en: "Strait of Malacca",
    lat: 2.5, lng: 102.0, category: "strategic-waterway",
    keywords: ["Malacca", "马六甲"],
  },
  {
    id: "ww-suez", name_zh: "苏伊士运河", name_en: "Suez Canal",
    lat: 30.5, lng: 32.3, category: "strategic-waterway",
    keywords: ["Suez", "苏伊士", "Egypt canal"],
  },
  {
    id: "ww-panama", name_zh: "巴拿马运河", name_en: "Panama Canal",
    lat: 9.1, lng: -79.7, category: "strategic-waterway",
    keywords: ["Panama Canal", "巴拿马运河"],
  },
  {
    id: "ww-bab", name_zh: "曼德海峡", name_en: "Bab el-Mandeb",
    lat: 12.6, lng: 43.4, category: "strategic-waterway",
    keywords: ["Bab el-Mandeb", "曼德", "Houthi", "胡塞", "Red Sea", "红海", "Yemen", "也门"],
  },
  {
    id: "ww-bosporus", name_zh: "博斯普鲁斯海峡", name_en: "Bosporus Strait",
    lat: 41.1, lng: 29.0, category: "strategic-waterway",
    keywords: ["Bosporus", "博斯普鲁斯", "Black Sea grain", "黑海粮"],
  },
  {
    id: "ww-cape", name_zh: "好望角", name_en: "Cape of Good Hope",
    lat: -34.4, lng: 18.5, category: "strategic-waterway",
    keywords: ["Cape of Good Hope", "好望角"],
  },
  {
    id: "ww-dover", name_zh: "多佛尔海峡", name_en: "Strait of Dover",
    lat: 51.0, lng: 1.5, category: "strategic-waterway",
    keywords: ["Dover", "多佛尔"],
  },
  {
    id: "ww-taiwan", name_zh: "台湾海峡", name_en: "Taiwan Strait",
    lat: 24.5, lng: 119.5, category: "strategic-waterway",
    keywords: ["Taiwan Strait", "台湾海峡", "台海"],
  },
  {
    id: "ww-gibraltar", name_zh: "直布罗陀海峡", name_en: "Strait of Gibraltar",
    lat: 35.97, lng: -5.5, category: "strategic-waterway",
    keywords: ["Gibraltar", "直布罗陀"],
  },
  {
    id: "ww-lombok", name_zh: "龙目海峡", name_en: "Lombok Strait",
    lat: -8.3, lng: 115.8, category: "strategic-waterway",
    keywords: ["Lombok"],
  },
  {
    id: "ww-singapore", name_zh: "新加坡海峡", name_en: "Singapore Strait",
    lat: 1.25, lng: 103.85, category: "strategic-waterway",
    keywords: ["Singapore Strait", "新加坡海峡"],
  },
  {
    id: "ww-danish", name_zh: "丹麦海峡", name_en: "Danish Straits",
    lat: 55.5, lng: 11.5, category: "strategic-waterway",
    keywords: ["Danish Straits", "Baltic Sea", "波罗的海", "丹麦海峡"],
  },
  {
    id: "ww-sicily", name_zh: "西西里海峡", name_en: "Sicily Channel",
    lat: 36.7, lng: 11.7, category: "strategic-waterway",
    keywords: ["Sicily Channel", "Mediterranean"],
  },
  {
    id: "ww-kerch", name_zh: "刻赤海峡", name_en: "Kerch Strait",
    lat: 45.3, lng: 36.6, category: "strategic-waterway",
    keywords: ["Kerch", "刻赤", "Crimea", "克里米亚", "Sea of Azov", "亚速海"],
  },

  // ===== Commodity hubs (17) =====
  {
    id: "ch-ghawar", name_zh: "Ghawar 油田", name_en: "Ghawar Oil Field",
    lat: 25.4, lng: 49.6, category: "commodity-hub", detail: "Oil (Saudi)",
    asset_ids: ["BRENT", "WTI"],
    keywords: ["Saudi", "沙特", "OPEC", "Ghawar"],
  },
  {
    id: "ch-permian", name_zh: "Permian 盆地", name_en: "Permian Basin",
    lat: 31.8, lng: -102.5, category: "commodity-hub", detail: "Oil (US shale)",
    asset_ids: ["WTI"],
    keywords: ["Permian", "shale", "US oil", "美国页岩"],
  },
  {
    id: "ch-pilbara", name_zh: "Pilbara 铁矿区", name_en: "Pilbara",
    lat: -22.5, lng: 118.0, category: "commodity-hub", detail: "Iron Ore (Australia)",
    keywords: ["iron ore", "铁矿", "Pilbara", "BHP", "Rio Tinto"],
  },
  {
    id: "ch-escondida", name_zh: "Escondida 铜矿", name_en: "Escondida Mine",
    lat: -24.3, lng: -69.1, category: "commodity-hub", detail: "Copper (Chile)",
    asset_ids: ["COPPER"],
    keywords: ["copper", "铜", "Chile", "智利", "Escondida"],
  },
  {
    id: "ch-katanga", name_zh: "Katanga 钴矿带", name_en: "Katanga Cobalt Belt",
    lat: -10.7, lng: 25.5, category: "commodity-hub", detail: "Cobalt (DRC)",
    keywords: ["cobalt", "钴", "DRC", "Congo", "刚果"],
  },
  {
    id: "ch-atacama", name_zh: "Atacama 锂三角", name_en: "Atacama Lithium Triangle",
    lat: -23.5, lng: -68.3, category: "commodity-hub", detail: "Lithium (Chile)",
    keywords: ["lithium", "锂", "Atacama", "智利锂"],
  },
  {
    id: "ch-norilsk", name_zh: "诺里尔斯克", name_en: "Norilsk",
    lat: 69.3, lng: 88.2, category: "commodity-hub", detail: "Palladium / Nickel (Russia)",
    keywords: ["palladium", "钯", "Norilsk", "Nornickel", "诺里尔斯克"],
  },
  {
    id: "ch-bushveld", name_zh: "Bushveld 铂矿带", name_en: "Bushveld Igneous Complex",
    lat: -24.7, lng: 27.4, category: "commodity-hub", detail: "Platinum (South Africa)",
    keywords: ["platinum", "铂", "Bushveld", "South Africa platinum", "南非铂"],
  },
  {
    id: "ch-sulawesi", name_zh: "苏拉威西镍矿", name_en: "Sulawesi Nickel Belt",
    lat: -2.7, lng: 121.4, category: "commodity-hub", detail: "Nickel (Indonesia)",
    keywords: ["nickel", "镍", "Sulawesi", "Indonesia nickel", "印尼镍"],
  },
  {
    id: "ch-bayan-obo", name_zh: "白云鄂博", name_en: "Bayan Obo",
    lat: 41.8, lng: 109.9, category: "commodity-hub", detail: "Rare Earth (China)",
    keywords: ["rare earth", "稀土", "Bayan Obo", "白云鄂博"],
  },
  {
    id: "ch-qatar-nf", name_zh: "Qatar North Field", name_en: "Qatar North Field",
    lat: 26.0, lng: 51.5, category: "commodity-hub", detail: "LNG (Qatar)",
    asset_ids: ["NATGAS"],
    keywords: ["LNG", "Qatar", "卡塔尔", "North Field"],
  },
  {
    id: "ch-yamal", name_zh: "亚马尔气田", name_en: "Yamal Gas Field",
    lat: 71.3, lng: 71.0, category: "commodity-hub", detail: "Gas (Russia)",
    asset_ids: ["NATGAS"],
    keywords: ["Yamal", "Gazprom", "Russia gas", "俄罗斯天然气", "亚马尔"],
  },
  {
    id: "ch-north-sea", name_zh: "北海油田", name_en: "Norwegian North Sea",
    lat: 60.0, lng: 2.0, category: "commodity-hub", detail: "Oil & Gas (Norway)",
    asset_ids: ["BRENT", "NATGAS"],
    keywords: ["North Sea", "Brent", "Norway oil", "挪威石油", "Equinor"],
  },
  {
    id: "ch-alberta", name_zh: "Alberta 油砂", name_en: "Alberta Oil Sands",
    lat: 57.0, lng: -111.5, category: "commodity-hub", detail: "Oil Sands (Canada)",
    asset_ids: ["WTI"],
    keywords: ["oil sands", "Alberta", "Canadian crude", "加拿大原油"],
  },
  {
    id: "ch-henry-hub", name_zh: "Henry Hub", name_en: "Henry Hub",
    lat: 30.0, lng: -92.7, category: "commodity-hub", detail: "Natural Gas pricing (US)",
    asset_ids: ["NATGAS"],
    keywords: ["Henry Hub", "natural gas"],
  },
  {
    id: "ch-carajas", name_zh: "Carajás 铁矿", name_en: "Carajás Mine",
    lat: -6.1, lng: -50.2, category: "commodity-hub", detail: "Iron Ore (Brazil)",
    keywords: ["iron ore", "铁矿", "Vale", "Carajás", "Brazil iron"],
  },
  {
    id: "ch-iowa", name_zh: "美国玉米带", name_en: "US Corn Belt (Iowa)",
    lat: 41.9, lng: -93.5, category: "commodity-hub", detail: "Corn & Soybean (US)",
    asset_ids: ["CORN", "SOYBEAN"],
    keywords: ["corn", "soybean", "玉米", "US grain", "US harvest", "美豆"],
  },
];
