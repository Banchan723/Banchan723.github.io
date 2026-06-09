---
title: "C++ const"
date: 2026-06-07
slug: "cpp-const"
description: "const = \"바뀌지 않는다\" 자물쇠. const 변수(고정값), const 멤버함수(함수() const=읽기전용 getter), const 참조(큰 객체 빨르고 안전하게)를 직접 돌려 확인. m.gethp 괄호 누락 에러 디버그."
categories:
  - "C++"
tags:
  - "const"
modality:
  - "code"
canonical_topic: "const"
topic_id: "cpp.const.basic"
context: "cpp"
level: "beginner"
---

## 이 글에서 이해할 것

const가 "바뀌지 않는다"는 자물쇠라는 것, 그리고 변수·멤버함수·참조 세 곳에 붙을 때 각각 무슨 뜻인지.

## 읽기 전 최소 배경

클래스와 멤버 함수, this->와 생성자를 안다고 가정한다. 점(`.`)으로 객체의 함수를 부른다는 것도.

## 내가 막혔던 점 / 틀린 가설

const를 함수에 붙일 때 `const void ...`처럼 함수 앞에 올 줄 알았다. 실제로 자주 쓰는 건 함수 이름 뒤에 붙는 const였다.

## 확인한 증거

const 멤버 함수를 직접 만들어 getter를 돌렸다.

```cpp
#include <iostream>
using namespace std;

class Monster
{
public:
    int hp = 110;

    Monster(int hp)
    {
        this->hp = hp;
    }

    int gethp() const     // 함수 이름 뒤에 const = 읽기 전용
    {
        return hp;        // 읽기만 함 (OK)
    }
};

int main()
{
    Monster m(100);
    cout << m.gethp();    // getter가 돌려준 hp 출력
    return 0;
}
```

직접 돌린 출력: `100`. 초기값 110을 주었지만 생성자의 `this->hp = hp`가 100으로 덮어썬고, getter가 그 100을 읽어서 돌려줬다.

처음엔 호출을 `m.gethp;`로 써서 에러가 났다. 함수를 호출하려면 괄호 `()`가 있어야 하고(`m.gethp()`), 그 결과를 출력하려면 `cout`에 넣어야 했다.

## 그래서 이렇게 이해했다

const는 "바뀌지 않는다"는 자물쇠다. 붙는 위치에 따라 뜻이 다르다.

const 변수는 고정값이다. 최대 체력이나 설정값처럼 변하면 안 되는 값에 붙이고, 바꿨려 하면 에러가 난다.

const 멤버 함수(`함수() const`)는 "이 함수는 객체를 읽기만 하고 수정 안 한다"는 약속이다. getter가 대표적인 예다. const는 함수 이름 뒤에 붙지, 함수 앞(`const void`)에 붙는 게 아니다.

const 참조는 큰 객체를 함수에 넘길 때 쓴다. 참조라 복사 없이 빨라고(속도), const라 함수가 원본을 실수로 바꾸는 것도 막는다(안전). 큰 데이터를 읽기 전용으로 넘길 때 딱이다.

## 다른 예시에 적용

언리얼 코드의 `GetHealth() const` 같은 getter들이 전부 이 패턴이다. 함수 뒤에 const가 붙으면 코드를 읽는 사람이 "이 함수 부르면 객체 상태가 안 바뀜"를 한눈에 알 수 있다.

## 아직 모르는 것

const 멤버 함수 안에서 멤버를 바꾸려 하면 캴파일 에러가 난다는 건 개념으로만 알 뿐 직접 돌려보진 않았고, 매개변수에 붙는 const는 아직이다.

## 확인 질문

`int gethp() const`의 const는 어디에 붙어 있고, 이 함수에 어떤 약속을 강제하는가? 그리고 이 함수를 호출하려면 main에서 어떻게 써야 하는가?
