function compare(a, b) {

  if (!compare.cache) {

    var pinnedCountryOrder = [
      "HK", "TW", "JP", "KR", "SG", "US"
    ];

    var defaultCountryOrder = [
      "IS", "NO", "CH", "DK", "DE", "SE", "AU", "HK", "NL", "BE", "IE", "FI", "SG", "GB",
      "AE", "CA", "LI", "NZ", "US", "KR", "SI", "AT", "JP", "MT", "LU", "FR", "IL", "ES",
      "CZ", "IT", "SM", "AD", "CY", "GR", "PL", "EE", "SA", "BH", "LT", "PT", "HR", "LV",
      "QA", "SK", "CL", "HU", "AR", "ME", "UY", "OM", "TR", "KW", "AG", "SC", "BG", "RO",
      "GE", "KN", "PA", "BN", "KZ", "CR", "RS", "RU", "BY", "BS", "MY", "MK", "AM", "BB",
      "AL", "TT", "MU", "BA", "IR", "VC", "TH", "CN", "PE", "GD", "AZ", "MX", "CO", "BR",
      "PW", "MD", "UA", "EC", "DO", "GY", "LK", "TO", "MV", "VN", "TM", "DZ", "CU", "DM",
      "PY", "EG", "JO", "LB", "LC", "MN", "TN", "ZA", "UZ", "BO", "GA", "MH", "BW", "FJ",
      "ID", "SR", "BZ", "LY", "JM", "KG", "PH", "MA", "VE", "WS", "NI", "NR", "BT", "SZ",
      "IQ", "TJ", "TV", "BD", "IN", "SV", "GQ", "PS", "CV", "NA", "GT", "CG", "HN", "KI",
      "ST", "TL", "GH", "KE", "NP", "VU", "LA", "AO", "FM", "MM", "KH", "KM", "ZW", "ZM",
      "CM", "SB", "CI", "UG", "RW", "PG", "TG", "SY", "MR", "NG", "TZ", "HT", "LS", "PK",
      "SN", "GM", "CD", "MW", "BJ", "GW", "DJ", "SD", "LR", "ER", "GN", "ET", "AF", "MZ",
      "MG", "YE", "SL", "BF", "BI", "ML", "NE", "TD", "CF", "SO", "SS", "KP", "MC", "TW"
    ];

    var pinnedCityOrder = {
      US: ["LAX"]
    };

    var defaultCityOrder = {
      AU: ["SYD"],
      US: ["LAX", "SJC", "SEA"],
      RU: ["MOW", "LED"]
    };

    function mergeUnique(pinned, defaults) {
      var result = [], seen = {};
      var arr = (pinned || []).concat(defaults || []);

      for (var i = 0; i < arr.length; i++) {
        if (!seen[arr[i]]) {
          seen[arr[i]] = true;
          result.push(arr[i]);
        }
      }

      return result;
    }

    function mergeCity(pinned, defaults) {
      var result = {}, keys = {};

      for (var k in pinned) keys[k] = true;
      for (var k in defaults) keys[k] = true;

      for (var country in keys) {
        result[country] = mergeUnique(pinned[country], defaults[country]);
      }

      return result;
    }

    function buildRank(list) {
      var map = {};

      for (var i = 0; i < list.length; i++) {
        map[list[i]] = i;
      }

      return map;
    }

    compare.cache = {
      countryRank: buildRank(
        mergeUnique(pinnedCountryOrder, defaultCountryOrder)
      ),
      cityRank: {}
    };

    var cityOrder = mergeCity(
      pinnedCityOrder,
      defaultCityOrder
    );


    for (var country in cityOrder) {
      compare.cache.cityRank[country] = buildRank(cityOrder[country]);
    }
  }

  function getRank(map, key) {
    return map[key] !== undefined ? map[key] : 99999;
  }

  function parse(name) {

    var parts = (name || "").trim().split(/\s+/);
    var region = (parts[1] || "").split("-");
    var index = parseInt(parts[2], 10);

    return {
      country: region[0] || "",
      city: region[1] || "",
      index: isNaN(index) ? 9999 : index,
      raw: name || ""
    };
  }

  var A = parse(a.Remark);
  var B = parse(b.Remark);

  var Acountry = getRank(compare.cache.countryRank, A.country);
  var Bcountry = getRank(compare.cache.countryRank, B.country);

  if (Acountry !== Bcountry) return Acountry < Bcountry;

  var Acity = compare.cache.cityRank[A.country]
    ? getRank(compare.cache.cityRank[A.country], A.city)
    : 99999;

  var Bcity = compare.cache.cityRank[B.country]
    ? getRank(compare.cache.cityRank[B.country], B.city)
    : 99999;

  if (Acity !== Bcity) return Acity < Bcity;

  if (A.index !== B.index) return A.index < B.index;

  return A.raw < B.raw;
}
